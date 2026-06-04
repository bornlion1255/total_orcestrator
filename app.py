import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import re
import time
import io
import json
from datetime import datetime

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="D2C · Оркестратор",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── ТЕМА ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background: #0D1117; color: #E6EDF3; }

[data-testid="stSidebar"] { background: #161B22; border-right: 1px solid #30363D; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div { color: #E6EDF3 !important; }

.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: #21262D !important; border: 1px solid #30363D !important;
    color: #E6EDF3 !important; border-radius: 6px !important; font-size: 13px !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: #21262D !important; border: 1px solid #30363D !important; color: #E6EDF3 !important;
}
span[data-baseweb="tag"] { background: #21262D !important; border: 1px solid #58A6FF !important; }
span[data-baseweb="tag"] span { color: #E6EDF3 !important; }
span[data-baseweb="tag"] button svg { fill: #8B949E !important; }

/* Основная кнопка (type="primary") */
[data-testid="baseButton-primary"] {
    background: #238636 !important; color: #fff !important; border: none !important;
    border-radius: 6px !important; font-weight: 700 !important;
    font-size: 14px !important; letter-spacing: .04em !important; transition: opacity .15s !important;
}
[data-testid="baseButton-primary"]:hover { opacity: .8 !important; }

/* Кнопка СТОП (type="secondary") */
[data-testid="baseButton-secondary"] {
    background: transparent !important; color: #F85149 !important;
    border: 1px solid #F85149 !important; border-radius: 6px !important;
    font-weight: 700 !important; font-size: 14px !important; transition: opacity .15s !important;
}
[data-testid="baseButton-secondary"]:hover { opacity: .7 !important; }

.stProgress > div > div > div { background: #58A6FF !important; }

[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #58A6FF !important; border-color: #58A6FF !important;
}

[data-testid="metric-container"] {
    background: #161B22 !important; border: 1px solid #30363D !important;
    border-radius: 8px !important; padding: 16px !important;
}
[data-testid="stFileUploader"] {
    background: #161B22 !important; border: 1px dashed #30363D !important; border-radius: 8px !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid #30363D !important; border-radius: 8px !important; overflow: hidden !important;
}

/* Вкладки */
.stTabs [data-testid="stTabBar"] {
    background: #161B22 !important; border-bottom: 1px solid #30363D !important; border-radius: 8px 8px 0 0;
}
.stTabs [data-testid="stTabBar"] button {
    color: #8B949E !important; font-weight: 600 !important; font-size: 13px !important;
    border-bottom: 2px solid transparent !important; border-radius: 0 !important; background: transparent !important;
}
.stTabs [data-testid="stTabBar"] button[aria-selected="true"] {
    color: #E6EDF3 !important; border-bottom: 2px solid #58A6FF !important; background: transparent !important;
}
.stTabs [data-testid="stTabPanel"] {
    background: #0D1117 !important; border: 1px solid #30363D !important;
    border-top: none !important; border-radius: 0 0 8px 8px; padding: 24px !important;
}

hr { border-color: #30363D !important; margin: 12px 0 !important; }
details summary { color: #8B949E !important; font-size: 13px !important; }
[data-testid="stExpander"] {
    background: #161B22 !important; border: 1px solid #30363D !important; border-radius: 6px !important;
}
#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] { background: #0D1117 !important; border-bottom: 1px solid #30363D; }

.log-box {
    background: #161B22; border: 1px solid #30363D; border-radius: 8px;
    padding: 12px 16px; font-family: 'SF Mono','Fira Code','Consolas',monospace;
    font-size: 12px; line-height: 1.9; max-height: 210px; overflow-y: auto;
}
.result-card {
    background: #161B22; border: 1px solid #30363D; border-radius: 8px;
    padding: 20px 24px; margin-top: 16px;
    font-family: 'SF Mono','Fira Code','Consolas',monospace;
    font-size: 13px; line-height: 2;
}
.result-ok   { border-left: 3px solid #3FB950; }
.result-fail { border-left: 3px solid #F85149; }
.tag-ok   { color: #3FB950; font-weight: 700; }
.tag-fail { color: #F85149; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── АВТОРИЗАЦИЯ ───────────────────────────────────────────────────────────────
def check_password() -> bool:
    if "APP_PASSWORD" not in st.secrets:
        return True
    if st.session_state.get("authed"):
        return True
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("## D2C · Оркестратор рассылок")
        pw = st.text_input("Пароль", type="password", key="pw_input")
        if st.button("Войти", use_container_width=True, type="primary"):
            if pw == st.secrets["APP_PASSWORD"]:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Неверный пароль")
    return False

if not check_password():
    st.stop()


# ── СЕКРЕТЫ ───────────────────────────────────────────────────────────────────
try:
    WA_TOKEN            = st.secrets["WA_TOKEN"]
    WA_INSTANCE_ID      = st.secrets["WA_INSTANCE_ID"]
    YANDEX_CASCADE_URL  = st.secrets["YANDEX_CASCADE_URL"]
    YANDEX_CLEANING_URL = st.secrets["YANDEX_CLEANING_URL"]
except KeyError as e:
    st.error(f"Отсутствует секрет: {e} — проверь .streamlit/secrets.toml")
    st.stop()

WA_API_URL   = f"https://api.1msg.io/{WA_INSTANCE_ID}/sendTemplate?token={WA_TOKEN}"
WA_NAMESPACE = "49276b64_15e7_414d_8f35_6ab04bcaa5b1"
CHANNEL_LABELS = {"max": "MAX", "tlgrm": "Telegram", "chat": "In-App Chat"}


# ── САЙДБАР ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## D2C · Оркестратор")
    st.caption(datetime.now().strftime("%d %b %Y  %H:%M"))
    st.markdown("---")

    st.markdown("**Направление**")
    business_unit = st.radio(
        "unit", ["Химчистка", "Клининг"], label_visibility="collapsed",
        help="Химчистка — HDE qlean  |  Клининг — HDE qlean2"
    )

    st.markdown("---")
    st.markdown("**Стратегия**")
    strategy_options = ["Каскад", "WhatsApp шаблон"] if business_unit == "Химчистка" else ["Каскад"]
    send_strategy = st.selectbox(
        "strategy", strategy_options, label_visibility="collapsed",
        help="Каскад — пробует каналы по очереди, для одного канала — оставь в списке только его\nWA шаблон — только Химчистка, требует одобренного шаблона"
    )

    st.markdown("---")

    cascade_order = []; wa_template = ""
    msg_text = ""; full_type_value = ""; tags_list = []

    if send_strategy == "Каскад":
        subject = st.text_input(
            "Тема", value="Клининг" if business_unit == "Клининг" else "Забытые вещи",
            help="Рассылка: <Тема> [XX] — суффикс обеспечивает повторный триггер правил HDE"
        )
        full_type_value = f"Рассылка: {subject}"

        msg_text = st.text_area("Сообщение", value="Текст сообщения...", height=110)
        char_count = len(msg_text)
        char_color = "#F85149" if char_count > 1024 else ("#D29922" if char_count > 820 else "#8B949E")
        st.markdown(
            f'<p style="font-size:11px;color:{char_color};margin-top:-10px">'
            f'{char_count} / 1024 символов</p>',
            unsafe_allow_html=True
        )

        tags_raw  = st.text_input("Теги (через запятую)", value="рассылка")
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        default_order = ["max", "tlgrm"] if business_unit == "Клининг" else ["chat", "tlgrm", "max"]
        cascade_order = st.multiselect(
            "Приоритет каналов (левый = первый)", ["max", "tlgrm", "chat"],
            default=default_order, format_func=lambda x: CHANNEL_LABELS[x],
            help="Для отправки в один канал — оставь только его в списке"
        )
    else:  # WhatsApp шаблон
        st.info("Перед использованием запросить шаблон у Льва Оганезова (l.oganezov@d2c.pro)")
        wa_template = st.text_input("Название шаблона", value="poteri",
                                    help="Шаблон должен быть одобрен в 1msg")

    st.markdown("---")
    delay_ms = st.slider("Задержка между отправками, мс", 100, 2000, 200, step=50)


# ── ФУНКЦИИ ОТПРАВКИ ──────────────────────────────────────────────────────────
def normalize_phone(phone: str) -> str:
    d = re.sub(r'\D', '', str(phone))
    if len(d) == 10: return "7" + d
    if len(d) == 11 and d.startswith('8'): return "7" + d[1:]
    return d

def _post(url: str, payload: dict) -> tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)

def send_himchistka_cascade(phone, msg, tv, tags, order):
    return _post(YANDEX_CASCADE_URL, {
        "phone": normalize_phone(phone), "message": msg, "type_value": tv,
        "tags": tags, "target_sources": order
    })

def send_cleaning_hde(phone, msg, tv, tags, order):
    return _post(YANDEX_CLEANING_URL, {
        "phone": normalize_phone(phone), "message": msg, "type_value": tv,
        "tags": tags, "target_sources": order
    })

def send_wa(phone, template):
    ok, raw = _post(WA_API_URL, {
        "template": template, "language": {"policy": "deterministic", "code": "ru"},
        "namespace": WA_NAMESPACE, "phone": normalize_phone(phone)
    })
    if ok:
        try:
            if json.loads(raw).get("sent"): return True, "sent"
        except Exception: pass
    return False, raw

def parse_response(ok: bool, raw: str) -> tuple[bool, str, str]:
    if not ok: return False, raw[:120], "—"
    try:
        body = json.loads(raw)
        return body.get("status") == "success", body.get("detail", ""), body.get("delivered_via", "—")
    except Exception:
        if "sent" in raw.lower(): return True, "WA доставлено", "whatsapp"
        return True, "200 OK", "—"

def dispatch(phone: str) -> tuple[bool, str, bool, str, str]:
    if business_unit == "Химчистка":
        if send_strategy == "Каскад":
            ok, raw = send_himchistka_cascade(phone, msg_text, full_type_value, tags_list, cascade_order)
        else:  # WhatsApp шаблон
            ok, raw = send_wa(phone, wa_template)
    else:  # Клининг
        ok, raw = send_cleaning_hde(phone, msg_text, full_type_value, tags_list, cascade_order)
    delivered, detail, channel = parse_response(ok, raw)
    return ok, raw, delivered, detail, channel


# ── СОСТОЯНИЕ РАССЫЛКИ ────────────────────────────────────────────────────────
for _k, _v in [("bc_stop", False), ("bc_results", []), ("bc_phones", [])]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

def _request_stop():
    st.session_state.bc_stop = True


# ── ВСПОМОГАТЕЛЬНЫЕ: DONUT + ТАБЛИЦА ─────────────────────────────────────────
def show_donut(series: pd.Series, title: str):
    if series.empty:
        st.caption("Нет данных")
        return
    colors = ["#58A6FF", "#3FB950", "#D29922", "#F85149", "#A371F7"]
    fig = go.Figure(go.Pie(
        labels=series.index.tolist(),
        values=series.values.tolist(),
        hole=0.55,
        textinfo="label+percent",
        marker=dict(colors=colors[:len(series)], line=dict(color="#0D1117", width=2)),
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="#0D1117", plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3", size=12),
        margin=dict(t=10, b=10, l=10, r=10),
        height=230,
        annotations=[dict(text=f"<b>{series.sum()}</b>", x=0.5, y=0.5,
                          font=dict(size=22, color="#E6EDF3"), showarrow=False)]
    )
    st.markdown(f"**{title}**")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def show_results(df: pd.DataFrame):
    total       = len(df)
    delivered_n = (df["Доставлено"] == "Да").sum()
    failed_n    = total - delivered_n

    st.markdown("---")
    st.markdown("### Результаты")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Всего",         total)
    m2.metric("Доставлено",    int(delivered_n), f"{delivered_n/total*100:.1f}%")
    m3.metric("Не доставлено", int(failed_n),    f"-{failed_n/total*100:.1f}%")
    m4.metric("Направление",   business_unit)

    st.markdown("")
    ch_col, err_col = st.columns(2)

    with ch_col:
        ch_data = df[df["Доставлено"] == "Да"]["Канал"].value_counts()
        show_donut(ch_data, "По каналам")

    with err_col:
        st.markdown("**Причины недоставки**")
        failed_df = df[df["Доставлено"] == "Нет"]
        if not failed_df.empty:
            reasons = failed_df["Детали"].value_counts().reset_index()
            reasons.columns = ["Причина", "Количество"]
            st.dataframe(reasons, use_container_width=True, hide_index=True)
        else:
            st.success("Ошибок нет")

    st.markdown("---")
    st.markdown("**Полный отчёт**")

    display_cols = ["Телефон", "Нормализован", "Доставлено", "Канал", "Детали"]
    display_df = df[display_cols].copy()

    def _row_color(row):
        if row["Доставлено"] == "Да":
            return ["background-color:#0a2010; color:#3FB950"] + ["background-color:#0a2010"] * (len(row)-1)
        return ["background-color:#200a0a; color:#F85149"] + ["background-color:#200a0a"] * (len(row)-1)

    try:
        st.dataframe(display_df.style.apply(_row_color, axis=1), use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Отчёт")
    fname = f"рассылка_{business_unit.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button("Скачать отчёт (.xlsx)", data=buf.getvalue(),
                       file_name=fname, mime="application/vnd.ms-excel", use_container_width=True)


# ── ГЛАВНАЯ ОБЛАСТЬ ───────────────────────────────────────────────────────────
unit_badge = "HDE · qlean" if business_unit == "Химчистка" else "HDE · qlean2"
st.markdown("# Оркестратор рассылок")
st.caption(f"Направление: **{business_unit}** ({unit_badge})  ·  Стратегия: **{send_strategy}**")
st.markdown("---")

cascade_blocked = send_strategy == "Каскад" and not cascade_order

tab_single, tab_bulk, tab_help = st.tabs(["Один номер", "Массовая рассылка", "Инструкция"])


# ══ ВКЛАДКА: ОДИН НОМЕР ══════════════════════════════════════════════════════
with tab_single:
    st.markdown("Отправка на один номер — удобно для тестирования.")
    st.markdown("")

    phone_input = st.text_input("Номер телефона", placeholder="79001234567", max_chars=20, key="single_phone")

    if send_strategy in ("Каскад", "Один канал"):
        with st.expander("Предпросмотр сообщения"):
            st.code(msg_text, language=None)
            st.caption(f"type_value: {full_type_value} [XX]  (XX — случайный двузначный суффикс)")

    if cascade_blocked:
        st.warning("Выберите хотя бы один канал в приоритете каскада.")
    else:
        if st.button("ОТПРАВИТЬ", use_container_width=True, key="btn_single", type="primary"):
            raw_phone = phone_input.strip()
            if not raw_phone:
                st.warning("Введите номер телефона.")
            else:
                with st.spinner("Отправка..."):
                    ok, raw, delivered, detail, channel = dispatch(raw_phone)
                norm      = normalize_phone(raw_phone)
                css_class = "result-ok" if delivered else "result-fail"
                s_html    = '<span class="tag-ok">ДОСТАВЛЕНО</span>' if delivered else '<span class="tag-fail">НЕ ДОСТАВЛЕНО</span>'
                via_line  = f"<br>Канал:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{channel}" if delivered else ""
                rsn_line  = f"<br>Причина:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{detail}" if detail else ""
                st.markdown(
                    f'<div class="result-card {css_class}">'
                    f'Статус:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{s_html}'
                    f'<br>Номер:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{norm}'
                    f'{via_line}{rsn_line}</div>',
                    unsafe_allow_html=True
                )
                with st.expander("Сырой ответ"):
                    st.code(raw, language="json")


# ══ ВКЛАДКА: МАССОВАЯ РАССЫЛКА ═══════════════════════════════════════════════
with tab_bulk:
    st.markdown("Загрузите Excel-файл. Первый столбец — номера телефонов, без заголовка.")
    st.markdown("")

    uploaded_file = st.file_uploader("Файл .xlsx", type=["xlsx"], label_visibility="collapsed")

    if uploaded_file:
        phones = []; parse_error = None
        try:
            df_input = pd.read_excel(uploaded_file, header=None)
            phones   = df_input.iloc[:, 0].dropna().astype(str).tolist()
            phones   = [p for p in phones if re.search(r'\d', p)]
        except Exception as e:
            parse_error = str(e)

        if parse_error:
            st.error(f"Ошибка чтения файла: {parse_error}")
        elif not phones:
            st.warning("В файле не найдено номеров телефонов.")
        else:
            # ── Дедупликация ─────────────────────────────────────────────────
            unique_phones = list(dict.fromkeys(phones))
            dup_count = len(phones) - len(unique_phones)
            if dup_count:
                st.warning(f"Найдено {dup_count} дублирующихся номеров — удалены автоматически. "
                           f"Осталось: {len(unique_phones)}.")
                phones = unique_phones

            # ── Pre-flight ────────────────────────────────────────────────────
            st.markdown("### Параметры запуска")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Получателей",    len(phones))
            c2.metric("Направление",    business_unit)
            c3.metric("Стратегия",      send_strategy)
            c4.metric("Оценка времени", f"~{int(len(phones)*(delay_ms/1000+0.6))} сек")

            if send_strategy in ("Каскад", "Один канал"):
                with st.expander("Предпросмотр сообщения"):
                    st.code(msg_text, language=None)
                    st.caption(f"type_value: {full_type_value} [XX]  (XX — случайный двузначный суффикс)")

            # ── Dry run ───────────────────────────────────────────────────────
            dry_run = st.checkbox(
                "Сухой прогон — проверить номера без отправки",
                help="Показывает нормализованные номера и флагирует подозрительные форматы. Сообщения НЕ отправляются."
            )

            if dry_run:
                validated = []
                for p in phones:
                    norm  = normalize_phone(p)
                    valid = len(norm) == 11 and norm.startswith("7")
                    validated.append({"Исходный": p, "Нормализован": norm,
                                      "Формат": "OK" if valid else "Проверить"})
                df_val   = pd.DataFrame(validated)
                issues   = df_val[df_val["Формат"] == "Проверить"]
                ok_count = len(df_val) - len(issues)

                col_ok, col_warn = st.columns(2)
                col_ok.metric("Корректный формат",  ok_count)
                col_warn.metric("Требуют проверки", len(issues))

                def _val_color(row):
                    if row["Формат"] == "OK":
                        return ["", "", "background-color:#0a2010; color:#3FB950"]
                    return ["", "", "background-color:#200a0a; color:#F85149"]
                try:
                    st.dataframe(df_val.style.apply(_val_color, axis=1),
                                 use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(df_val, use_container_width=True, hide_index=True)

            else:
                st.markdown("---")

                if cascade_blocked:
                    st.warning("Выберите хотя бы один канал в приоритете каскада.")
                else:
                    launch_col, stop_col = st.columns([3, 1])
                    launch_clicked = launch_col.button(
                        "ЗАПУСТИТЬ РАССЫЛКУ", use_container_width=True, key="btn_bulk", type="primary"
                    )
                    stop_col.button(
                        "СТОП", on_click=_request_stop,
                        type="secondary", use_container_width=True, key="btn_stop",
                        help="Останавливает рассылку после текущего номера"
                    )

                    if launch_clicked:
                        st.session_state.bc_stop    = False
                        st.session_state.bc_results = []
                        st.session_state.bc_phones  = phones

                        progress_bar = st.progress(0, text="Запуск...")
                        log_slot     = st.empty()
                        log_lines: list[str] = []
                        t_start      = time.time()

                        for i, phone in enumerate(phones):
                            if st.session_state.bc_stop:
                                st.warning(f"Рассылка остановлена. Обработано: {i} из {len(phones)}.")
                                break

                            ok_flag, raw, delivered, detail, channel = dispatch(phone)
                            norm = normalize_phone(phone)

                            result = {
                                "Телефон": phone, "Нормализован": norm,
                                "Доставлено": "Да" if delivered else "Нет",
                                "Канал": channel, "Детали": detail, "Raw": raw[:200],
                            }
                            st.session_state.bc_results.append(result)

                            ts    = datetime.now().strftime("%H:%M:%S")
                            color = "#3FB950" if delivered else "#F85149"
                            label = "OK  " if delivered else "FAIL"
                            via   = channel if delivered else detail[:55]
                            log_lines.append(
                                f'<span style="color:{color}">[{ts}]  [{label}]  {norm}  {via}</span>'
                            )
                            if len(log_lines) > 14:
                                log_lines = log_lines[-14:]
                            log_slot.markdown(
                                f'<div class="log-box">{"<br>".join(log_lines)}</div>',
                                unsafe_allow_html=True
                            )

                            done = i + 1
                            elapsed = time.time() - t_start
                            rate    = done / elapsed if elapsed > 0 else 1
                            eta     = int((len(phones) - done) / rate)
                            progress_bar.progress(
                                done / len(phones),
                                text=f"{done} / {len(phones)}  |  ETA {eta} сек"
                            )
                            time.sleep(delay_ms / 1000)

                        log_slot.empty()
                        progress_bar.empty()

                    if st.session_state.bc_results:
                        show_results(pd.DataFrame(st.session_state.bc_results))


# ══ ВКЛАДКА: ИНСТРУКЦИЯ ══════════════════════════════════════════════════════
with tab_help:
    st.markdown("""
### Быстрый старт

**1. Выберите направление** в левой панели:
- **Химчистка** — рассылки в HDE пространство qlean
- **Клининг** — рассылки в HDE пространство qlean2

**2. Выберите стратегию:**

| Стратегия | Описание |
|-----------|----------|
| Каскад | Проверяет каналы слева направо, отправляет в первый найденный активный диалог |
| Один канал | Отправляет строго в выбранный канал. Нет диалога — не доставлено |
| WA шаблон | Прямая отправка одобренного шаблона через 1msg (только Химчистка) |

**3. Заполните параметры:**
- **Тема** — попадает в поле `type_value` тикета в HDE. К теме автоматически добавляется случайный суффикс `[12]`, чтобы правила в HDE срабатывали при повторной рассылке с тем же названием.
- **Сообщение** — текст, который получит клиент. Лимит 1024 символа (WhatsApp).
- **Теги** — проставляются на тикет через запятую.

---

### Один номер

Используй для тестирования перед массовой рассылкой. Введи номер в любом формате — система сама нормализует его.

**Поддерживаемые форматы:** `79001234567` · `89001234567` · `9001234567` · `+79001234567`

---

### Массовая рассылка

**Формат файла:** Excel (.xlsx), первый столбец — номера телефонов, без заголовка.

**Порядок действий:**
1. Загрузи файл
2. Проверь параметры в блоке «Параметры запуска»
3. При необходимости включи **Сухой прогон** — проверит форматы номеров без отправки
4. Нажми **Запустить рассылку**
5. Следи за лайв-логом
6. После завершения скачай отчёт

**Кнопка СТОП** — останавливает рассылку после текущего номера. Уже отправленные результаты сохранятся и будут показаны в отчёте.

---

### Каналы

| Ключ | Канал |
|------|-------|
| max | MAX |
| tlgrm | Telegram |
| chat | In-App Chat |

**Рекомендуемый каскад для Химчистки:** chat → tlgrm → max
**Рекомендуемый каскад для Клининга:** max → tlgrm

---

### Отчёт

После рассылки доступна таблица с результатами:
- Зелёные строки — доставлено
- Красные строки — не доставлено, в колонке «Детали» указана причина

Скачай `.xlsx` для дальнейшей работы (повторная отправка по failed, аналитика и т.д.).

---

### Частые причины недоставки

| Причина | Что делать |
|---------|-----------|
| `User not found` | Клиент не зарегистрирован в HDE |
| `No dialog found` | У клиента нет активного диалога в выбранном канале |
| `HDE Send Error` | Ошибка API — проверь статус HDE |
| Ошибка сети | Проблема с Яндекс Клауд функцией |
""")
