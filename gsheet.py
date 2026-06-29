"""Thin Google Sheet adapter — durable mirror of broadcast progress.

Design goals:
- Optional: if creds/sheet are missing or gspread isn't installed, every method is a
  safe no-op. The local jsonl checkpoint stays the source of truth, the app never breaks.
- Never raises into the worker thread: all Sheet calls swallow exceptions (logged in
  `errors`) so a flaky network can't abort a broadcast.
"""
from __future__ import annotations

import re
from typing import Any

RUNS_HEADER = [
    "run_id", "started_at", "updated_at", "unit", "strategy",
    "subject", "total", "processed", "delivered", "failed", "status",
]
RESULTS_HEADER = [
    "run_id", "ts", "index", "phone", "normalized", "delivered", "channel", "detail",
]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GSheetSink:
    def __init__(self, service_account_info: dict | None, sheet_id: str | None):
        self.enabled = False
        self.error = ""
        self.errors: list[str] = []
        self._sheet_id = sheet_id
        self._sa = service_account_info
        self._sh = None
        self._runs_ws = None
        self._results_ws = None
        self._run_rows: dict[str, int] = {}

        if service_account_info and sheet_id:
            try:
                self._connect()
                self.enabled = True
            except Exception as e:  # missing lib, bad creds, no access — degrade silently
                self.error = f"{type(e).__name__}: {e}"

    # ── connection ────────────────────────────────────────────────────────────
    def _connect(self) -> None:
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_info(self._sa, scopes=SCOPES)
        gc = gspread.authorize(creds)
        self._sh = gc.open_by_key(self._sheet_id)
        self._runs_ws = self._ensure_ws("runs", RUNS_HEADER)
        self._results_ws = self._ensure_ws("results", RESULTS_HEADER)

    def _ensure_ws(self, title: str, header: list[str]):
        import gspread
        try:
            ws = self._sh.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self._sh.add_worksheet(title=title, rows=2000, cols=max(12, len(header)))
            ws.append_row(header, value_input_option="RAW")
            return ws
        if ws.row_values(1)[: len(header)] != header:
            ws.update(range_name="A1", values=[header])
        return ws

    # ── writes (no-op + swallow when disabled/erroring) ─────────────────────────
    def upsert_run(self, summary: dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        values = [summary.get(h, "") for h in RUNS_HEADER]
        rid = summary["run_id"]
        try:
            row = self._run_rows.get(rid) or self._find_run_row(rid)
            if row:
                self._runs_ws.update(range_name=f"A{row}", values=[values])
            else:
                resp = self._runs_ws.append_row(values, value_input_option="RAW")
                rng = resp["updates"]["updatedRange"].split("!")[1]
                self._run_rows[rid] = int(re.search(r"(\d+)", rng).group(1))
            return True
        except Exception as e:
            self.errors.append(str(e))
            return False

    def append_results(self, run_id: str, records: list[dict]) -> bool:
        if not self.enabled or not records:
            return False
        rows = [
            [
                run_id, r["ts"], r["index"], r["phone"], r["normalized"],
                "Да" if r["delivered"] else "Нет", r["channel"], r["detail"],
            ]
            for r in records
        ]
        try:
            self._results_ws.append_rows(rows, value_input_option="RAW")
            return True
        except Exception as e:
            self.errors.append(str(e))
            return False

    def _find_run_row(self, run_id: str) -> int | None:
        try:
            cell = self._runs_ws.find(run_id, in_column=1)
            if cell:
                self._run_rows[run_id] = cell.row
                return cell.row
        except Exception:
            pass
        return None

    def test_connection(self) -> tuple[bool, str]:
        if not self._sa or not self._sheet_id:
            return False, "Секреты gcp_service_account / GSHEET_ID не заданы"
        if not self.enabled:
            return False, self.error or "Не удалось подключиться"
        try:
            return True, f"OK — таблица «{self._sh.title}»"
        except Exception as e:
            return False, str(e)
