"""Broadcast engine — decoupled from the Streamlit script run.

The send loop runs in a background daemon thread held by a process-wide singleton
(`BroadcastManager`, created via @st.cache_resource in the app). That means a browser
tab disconnect / network blip no longer aborts a broadcast: the thread keeps going and
checkpoints every phone to `runs/{run_id}.jsonl`, so progress survives and can be resumed
without re-sending. Google Sheet (optional) is a durable mirror behind a thin sink.

This module is Streamlit-free on purpose (thread-safe, testable). The app snapshots all
sidebar params + secrets into BroadcastParams at launch and passes them in.
"""
from __future__ import annotations

import json
import re
import threading
import time
import random
import requests
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

# ── parameter snapshot (immutable per run; secrets are NOT persisted) ───────────
SECRET_FIELDS = {"yandex_cascade_url", "yandex_cleaning_url", "wa_api_url", "wa_namespace"}


@dataclass
class BroadcastParams:
    business_unit: str          # "Химчистка" | "Клининг"
    send_strategy: str          # "Каскад" | "WhatsApp шаблон"
    msg_text: str
    type_value: str             # "Рассылка: {subject}"
    tags: list[str]
    cascade_order: list[str]
    wa_template: str
    delay_ms: int
    # secrets — supplied at runtime, never written to the manifest
    yandex_cascade_url: str = ""
    yandex_cleaning_url: str = ""
    wa_api_url: str = ""
    wa_namespace: str = ""

    def to_manifest(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in SECRET_FIELDS}

    @classmethod
    def from_manifest(cls, m: dict, **secrets) -> "BroadcastParams":
        base = {k: v for k, v in m.items() if k in cls.__dataclass_fields__}
        return cls(**base, **secrets)


# ── pure send logic (moved out of orchestrator so the worker has no st.* deps) ──
PHONE_RE = re.compile(r"^7\d{10}$")


def normalize_phone(phone: str) -> str:
    d = re.sub(r"\D", "", str(phone))
    if len(d) == 10:
        return "7" + d
    if len(d) == 11 and d.startswith("8"):
        return "7" + d[1:]
    return d


def is_valid_phone(norm: str) -> bool:
    """Годен к отправке только российский номер ровно 7XXXXXXXXXX.

    Не косметика. Поиск пользователя в HDE (`?search=`) работает по ПРЕФИКСУ:
    `search=7` возвращает сотни чужих людей. Любой огрызок цифр, пропущенный
    дальше, находит случайного абонента и рассылка уходит не тому. Так 25.08.2026
    из-за столбца с email вместо телефонов ("novkot16@yandex.ru" -> "16") ушло
    477 сообщений посторонним.
    """
    return bool(PHONE_RE.match(norm))


def pick_phone_column(df) -> tuple[int, str]:
    """Столбец с телефонами = где больше всего значений проходят is_valid_phone.

    Слепой iloc[:, 0] брал первый столбец каким бы он ни был; в выгрузке с
    email'ами в первой колонке это и стало началом аварии.
    """
    best_idx, best_hits = 0, -1
    for i in range(df.shape[1]):
        col = df.iloc[:, i].dropna().astype(str)
        hits = sum(1 for v in col if is_valid_phone(normalize_phone(v)))
        if hits > best_hits:
            best_idx, best_hits = i, hits
    total = len(df.iloc[:, best_idx].dropna())
    note = f"столбец {best_idx + 1}: {best_hits} из {total} похожи на телефон"
    return best_idx, note


def _post(url: str, payload: dict) -> tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)


def _send_hde(url: str, norm: str, p: BroadcastParams) -> tuple[bool, str]:
    return _post(url, {
        "phone": norm, "message": p.msg_text, "type_value": p.type_value,
        "tags": p.tags, "target_sources": p.cascade_order,
    })


def _send_wa(norm: str, p: BroadcastParams) -> tuple[bool, str]:
    ok, raw = _post(p.wa_api_url, {
        "template": p.wa_template, "language": {"policy": "deterministic", "code": "ru"},
        "namespace": p.wa_namespace, "phone": norm,
    })
    if ok:
        try:
            if json.loads(raw).get("sent"):
                return True, "sent"
        except Exception:
            pass
    return False, raw


def parse_response(ok: bool, raw: str) -> tuple[bool, str, str]:
    if not ok:
        return False, raw[:120], "—"
    try:
        body = json.loads(raw)
        return body.get("status") == "success", body.get("detail", ""), body.get("delivered_via", "—")
    except Exception:
        if "sent" in raw.lower():
            return True, "WA доставлено", "whatsapp"
        return True, "200 OK", "—"


def dispatch_one(p: BroadcastParams, phone: str) -> dict:
    norm = normalize_phone(phone)
    # Последний рубеж: ни один запрос не уходит, пока номер не подтверждён.
    if not is_valid_phone(norm):
        return {"normalized": norm, "delivered": False, "channel": "—",
                "detail": "Некорректный номер — не отправлено", "raw": ""}
    if p.business_unit == "Химчистка":
        if p.send_strategy == "Каскад":
            ok, raw = _send_hde(p.yandex_cascade_url, norm, p)
        else:
            ok, raw = _send_wa(norm, p)
    else:
        ok, raw = _send_hde(p.yandex_cleaning_url, norm, p)
    delivered, detail, channel = parse_response(ok, raw)
    return {"normalized": norm, "delivered": delivered, "detail": detail,
            "channel": channel, "raw": raw}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── run state (lives in memory in the singleton; mirrored to disk per phone) ────
@dataclass
class RunState:
    run_id: str
    phones: list[str]
    manifest: dict
    total: int
    processed: int = 0
    delivered: int = 0
    failed: int = 0
    status: str = "running"     # running | completed | stopped | error
    started_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    error: str = ""
    recent_log: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> dict:
        with self._lock:
            done = self.processed
            elapsed = max((datetime.fromisoformat(_now()) -
                           datetime.fromisoformat(self.started_at)).total_seconds(), 0.001)
            rate = done / elapsed if done else 0
            remaining = self.total - done
            eta = int(remaining / rate) if rate > 0 and remaining > 0 else 0
            return {
                "run_id": self.run_id, "total": self.total, "processed": done,
                "delivered": self.delivered, "failed": self.failed, "status": self.status,
                "error": self.error, "eta": eta, "recent_log": list(self.recent_log),
                "started_at": self.started_at, "updated_at": self.updated_at,
            }


class BroadcastManager:
    SHEET_BATCH = 25
    SHEET_FLUSH_SEC = 10

    def __init__(self, runs_dir: str | Path):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    # ── paths ───────────────────────────────────────────────────────────────
    def _manifest_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.manifest.json"

    def _jsonl_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.jsonl"

    # ── public API ────────────────────────────────────────────────────────────
    def start(self, params: BroadcastParams, phones: list[str], sink=None) -> str:
        # Двойной клик по «Запустить» (или две вкладки разом) поднимал два воркера
        # на один список — каждый получатель ловил сообщение дважды.
        active = self.active_run_id()
        if active:
            raise RuntimeError(f"Рассылка {active} уже идёт — дождитесь конца или нажмите СТОП.")
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest = {
            "run_id": run_id, "started_at": _now(), "status": "running",
            "total": len(phones), "params": params.to_manifest(), "phones": phones,
        }
        self._write_manifest(manifest)
        state = RunState(run_id=run_id, phones=phones, manifest=manifest, total=len(phones))
        with self._lock:
            self.runs[run_id] = state
        self._spawn(state, params, sink, start_index=0)
        return run_id

    def resume(self, run_id: str, params: BroadcastParams, sink=None) -> bool:
        manifest = self.load_manifest(run_id)
        if not manifest:
            return False
        phones = manifest["phones"]
        start_index = self._processed_count(run_id)
        if start_index >= len(phones):
            return False
        done = self._tally(run_id)
        state = RunState(
            run_id=run_id, phones=phones, manifest=manifest, total=len(phones),
            processed=start_index, delivered=done["delivered"], failed=done["failed"],
            status="running", started_at=manifest.get("started_at", _now()),
        )
        with self._lock:
            self.runs[run_id] = state
        manifest["status"] = "running"
        self._write_manifest(manifest)
        self._spawn(state, params, sink, start_index=start_index)
        return True

    def stop(self, run_id: str) -> None:
        st = self.get(run_id)
        if st:
            st._stop.set()

    def get(self, run_id: str) -> RunState | None:
        return self.runs.get(run_id)

    def active_run_id(self) -> str | None:
        for rid, st in self.runs.items():
            if st.status == "running":
                return rid
        return None

    def list_runs(self) -> list[dict]:
        """History rows from disk (survives reruns; interrupted = manifest says running
        but no live thread, e.g. after an instance restart)."""
        out = []
        for mf in self.runs_dir.glob("*.manifest.json"):
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            rid = m["run_id"]
            tally = self._tally(rid)
            status = m.get("status", "running")
            live = self.runs.get(rid)
            if live:
                status = live.status
            elif status == "running":
                status = "interrupted"
            out.append({
                "run_id": rid, "started_at": m.get("started_at", ""),
                "unit": m.get("params", {}).get("business_unit", ""),
                "strategy": m.get("params", {}).get("send_strategy", ""),
                "subject": m.get("params", {}).get("type_value", ""),
                "total": m.get("total", 0), "processed": tally["processed"],
                "delivered": tally["delivered"], "failed": tally["failed"],
                "status": status,
            })
        return sorted(out, key=lambda r: r["started_at"], reverse=True)

    def load_manifest(self, run_id: str) -> dict | None:
        p = self._manifest_path(run_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def read_results(self, run_id: str) -> list[dict]:
        p = self._jsonl_path(run_id)
        if not p.exists():
            return []
        rows = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
        return rows

    def remaining_phones(self, run_id: str) -> list[str]:
        m = self.load_manifest(run_id)
        if not m:
            return []
        return m["phones"][self._processed_count(run_id):]

    # ── internals ─────────────────────────────────────────────────────────────
    def _spawn(self, state: RunState, params: BroadcastParams, sink, start_index: int):
        t = threading.Thread(target=self._worker, args=(state, params, sink, start_index),
                             daemon=True)
        state._thread = t
        t.start()

    def _worker(self, state: RunState, params: BroadcastParams, sink, start_index: int):
        buffer: list[dict] = []
        last_flush = time.time()
        self._sheet_summary(sink, state)
        try:
            completed = True
            for i in range(start_index, state.total):
                if state._stop.is_set():
                    self._set_status(state, "stopped")
                    completed = False
                    break

                res = dispatch_one(params, state.phones[i])
                ts = _now()
                record = {"index": i, "ts": ts, "phone": state.phones[i],
                          "normalized": res["normalized"], "delivered": res["delivered"],
                          "channel": res["channel"], "detail": res["detail"]}
                self._append_jsonl(state.run_id, record)

                with state._lock:
                    state.processed = i + 1
                    if res["delivered"]:
                        state.delivered += 1
                    else:
                        state.failed += 1
                    state.results.append({**record, "raw": res["raw"][:200]})
                    tag = "OK  " if res["delivered"] else "FAIL"
                    via = res["channel"] if res["delivered"] else res["detail"][:55]
                    state.recent_log.append(f'[{ts[11:19]}] [{tag}] {res["normalized"]}  {via}')
                    state.recent_log = state.recent_log[-15:]
                    state.updated_at = ts

                if sink and sink.enabled:
                    buffer.append(record)
                    if len(buffer) >= self.SHEET_BATCH or (time.time() - last_flush) >= self.SHEET_FLUSH_SEC:
                        sink.append_results(state.run_id, buffer)
                        buffer = []
                        self._sheet_summary(sink, state)
                        last_flush = time.time()

                time.sleep(params.delay_ms / 1000)

            if completed:
                self._set_status(state, "completed")
        except Exception as e:
            self._set_status(state, "error", str(e))

        if sink and sink.enabled and buffer:
            sink.append_results(state.run_id, buffer)
        self._sheet_summary(sink, state)
        self._update_manifest_status(state.run_id, state.status)

    def _set_status(self, state: RunState, status: str, error: str = ""):
        with state._lock:
            state.status = status
            state.error = error
            state.updated_at = _now()

    def _sheet_summary(self, sink, state: RunState):
        if not sink or not sink.enabled:
            return
        snap = state.snapshot()
        sink.upsert_run({
            "run_id": state.run_id, "started_at": state.started_at, "updated_at": snap["updated_at"],
            "unit": state.manifest.get("params", {}).get("business_unit", ""),
            "strategy": state.manifest.get("params", {}).get("send_strategy", ""),
            "subject": state.manifest.get("params", {}).get("type_value", ""),
            "total": state.total, "processed": snap["processed"],
            "delivered": snap["delivered"], "failed": snap["failed"], "status": snap["status"],
        })

    # ── disk checkpoint ─────────────────────────────────────────────────────────
    def _write_manifest(self, manifest: dict):
        self._manifest_path(manifest["run_id"]).write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def _update_manifest_status(self, run_id: str, status: str):
        m = self.load_manifest(run_id)
        if m:
            m["status"] = status
            m["finished_at"] = _now()
            self._write_manifest(m)

    def _append_jsonl(self, run_id: str, record: dict):
        with self._jsonl_path(run_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _processed_count(self, run_id: str) -> int:
        p = self._jsonl_path(run_id)
        if not p.exists():
            return 0
        return sum(1 for line in p.read_text(encoding="utf-8").splitlines() if line.strip())

    def _tally(self, run_id: str) -> dict:
        delivered = processed = 0
        for r in self.read_results(run_id):
            processed += 1
            if r.get("delivered"):
                delivered += 1
        return {"processed": processed, "delivered": delivered, "failed": processed - delivered}
