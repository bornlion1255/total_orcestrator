import streamlit as st
import pandas as pd
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
/* База */
.stApp { background: #0D1117; color: #E6EDF3; }

/* Сайдбар */
[data-testid="stSidebar"] {
    background: #161B22;
    border-right: 1px solid #30363D;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div { color: #E6EDF3 !important; }

/* Инпуты */
.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: #21262D !important;
    border: 1px solid #30363D !important;
    color: #E6EDF3 !important;
    border-radius: 6px !important;
    font-size: 13px !important;
}

/* Селекты */
.stSelectbox   > div > div,
.stMultiSelect > div > div {
    background: #21262D !important;
    border: 1px solid #30363D !important;
    color: #E6EDF3 !important;
}

/* Теги в мультиселекте (чипсы MAX, Telegram и т.п.) */
span[data-baseweb="tag"] {
    background: #21262D !important;
    border: 1px solid #58A6FF !important;
}
span[data-baseweb="tag"] span { color: #E6EDF3 !important; }
span[data-baseweb="tag"] button svg { fill: #8B949E !important; }

/* Кнопка */
.stButton > button {
    background: #238636 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    letter-spacing: .04em !important;
    transition: opacity .15s !important;
}
.stButton > button:hover { opacity: .8 !important; }

/* Прогресс */
.stProgress > div > div > div { background: #58A6FF !important; }

/* Слайдер */
[data-testid="stSlider"] [data-baseweb="slider"] [data-baseweb="slider-inner-thumb"],
[data-testid="stSlider"] [data-baseweb="slider"] [data-baseweb="slider-thumb"] {
    background: #58A6FF !important;
    border-color: #58A6FF !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
    background: #58A6FF !important;
    border-color: #58A6FF !important;
}

/* Метрики */
[data-testid="metric-container"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    padding: 16px !important;
}

/* Загрузчик файла */
[data-testid="stFileUploader"] {
    background: #161B22 !important;
    border: 1px dashed #30363D !important;
    border-radius: 8px !important;
}

/* Датафрейм */
[data-testid="stDataFrame"] {
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* Вкладки — панель */
.stTabs [data-testid="stTabBar"] {
    background: #161B22 !important;
    border-bottom: 1px solid #30363D !important;
    border-radius: 8px 8px 0 0;
    gap: 0;
}
/* Вкладки — обычная */
.stTabs [data-testid="stTabBar"] button {
    color: #8B949E !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    background: transparent !important;
}
/* Вкладки — активная */
.stTabs [data-testid="stTabBar"] button[aria-selected="true"] {
    color: #E6EDF3 !important;
    border-bottom: 2px solid #58A6FF !important;
    background: transparent !important;
}
/* Вкладки — контент */
.stTabs [data-testid="stTabPanel"] {
    background: #0D1117 !important;
    border: 1px solid #30363D !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px;
    padding: 24px !important;
}

/* Разделитель */
hr { border-color: #30363D !important; margin: 12px 0 !important; }

/* Экспандер */
details summary { color: #8B949E !important; font-size: 13px !important; }
[data-testid="stExpander"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
    border-radius: 6px !important;
}

/* Скрыть Streamlit-хром */
#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] {
    background: #0D1117 !important;
    border-bottom: 1px solid #30363D;
}

/* Лайв-лог */
.log-box {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.9;
    max-height: 210px;
    overflow-y: auto;
}

/* Карточка результата (одиночный номер) */
.result-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 20px 24px;
    margin-top: 16px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 2;
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
        if st.button("Войти", use_container_width=True):
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
    YANDEX_SINGLE_URL   = st.secrets["YANDEX_SINGLE_URL"]
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
        "unit",
        ["Химчистка", "Клининг"],
        label_visibility="collapsed",
        help="Химчистка — HDE qlean  |  Клининг — HDE qlean2"
    )

    st.markdown("---")
    st.markdown("**Стратегия**")
    strategy_options = (
        ["Каскад", "Один канал"]
        if business_unit == "Клининг"
        else ["Каскад", "Один канал", "WhatsApp шаблон"]
    )
    send_strategy = st.selectbox(
        "strategy",
        strategy_options,
        label_visibility="collapsed",
        help=(
            "Каскад — пробует каналы по порядку, первый найденный побеждает\n"
            "Один канал — только указанный канал\n"
            "WhatsApp шаблон — прямая отправка одобренного шаблона (только Химчистка)"
        )
    )

    st.markdown("---")

    cascade_order   = []
    target_source   = "chat"
    wa_template     = ""
    msg_text        = ""
    full_type_value = ""
    tags_list       = []

    if send_strategy in ("Каскад", "Один канал"):
        default_subject = "Клининг" if business_unit == "Клининг" else "Забытые вещи"
        subject = st.text_input(
            "Тема",
            value=default_subject,
            help="Подставляется в type_value: Рассылка: <Тема> [XX]"
        )
        full_type_value = f"Рассылка: {subject}"

        msg_text = st.text_area("Сообщение", value="Текст сообщения...", height=110)

        tags_raw  = st.text_input("Теги (через запятую)", value="рассылка")
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        if send_strategy == "Каскад":
            default_order = ["max", "tlgrm"] if business_unit == "Клининг" else ["chat", "tlgrm", "max"]
            cascade_order = st.multiselect(
                "Приоритет каналов (левый = первый)",
                options=["max", "tlgrm", "chat"],
                default=default_order,
                format_func=lambda x: CHANNEL_LABELS[x]
            )
        else:
            target_source = st.selectbox(
                "Канал",
                ["chat", "tlgrm", "max"],
                format_func=lambda x: CHANNEL_LABELS[x]
            )

    else:  # WhatsApp шаблон
        wa_template = st.text_input(
            "Название шаблона",
            value="poteri",
            help="Шаблон должен быть одобрен в 1msg"
        )

    st.markdown("---")
    delay_ms = st.slider("Задержка между отправками, мс", 100, 2000, 200, step=50)


# ── ФУНКЦИИ ОТПРАВКИ ──────────────────────────────────────────────────────────
def normalize_phone(phone: str) -> str:
    d = re.sub(r'\D', '', str(phone))
    if len(d) == 10:                        return "7" + d
    if len(d) == 11 and d.startswith('8'): return "7" + d[1:]
    return d

def _post(url: str, payload: dict) -> tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200, r.text
    except Exception as e:
        return False, str(e)

def send_himchistka_cascade(phone, message, type_value, tags, order):
    return _post(YANDEX_CASCADE_URL, {
        "phone": normalize_phone(phone), "message": message,
        "type_value": type_value, "tags": tags, "target_sources": order
    })

def send_himchistka_single(phone, message, type_value, tags, source):
    return _post(YANDEX_SINGLE_URL, {
        "phone": normalize_phone(phone), "message": message,
        "type_value": type_value, "tags": tags, "target_source": source
    })

def send_cleaning_hde(phone, message, type_value, tags, strategy, cascade_order=None, source=None):
    payload = {
        "phone": normalize_phone(phone), "message": message,
        "type_value": type_value, "tags": tags
    }
    payload["target_sources" if strategy == "Каскад" else "target_source"] = (
        cascade_order if strategy == "Каскад" else source
    )
    return _post(YANDEX_CLEANING_URL, payload)

def send_wa_template(phone, template):
    ok, raw = _post(WA_API_URL, {
        "template": template,
        "language": {"policy": "deterministic", "code": "ru"},
        "namespace": WA_NAMESPACE,
        "phone": normalize_phone(phone)
    })
    if ok:
        try:
            if json.loads(raw).get("sent"):
                return True, "sent"
        except Exception:
            pass
    return False, raw

def parse_response(ok: bool, raw: str) -> tuple[bool, str, str]:
    """Возвращает (доставлено, детали, канал)"""
    if not ok:
        return False, raw[:120], "—"
    try:
        body = json.loads(raw)
        delivered = body.get("status") == "success"
        return delivered, body.get("detail", ""), body.get("delivered_via", "—")
    except Exception:
        if "sent" in raw.lower():
            return True, "WA доставлено", "whatsapp"
        return True, "200 OK", "—"

def dispatch(phone: str) -> tuple[bool, str, bool, str, str]:
    """Маршрутизация одного номера. Возвращает (ok, raw, доставлено, детали, канал)."""
    if business_unit == "Химчистка":
        if send_strategy == "Каскад":
            ok, raw = send_himchistka_cascade(phone, msg_text, full_type_value, tags_list, cascade_order)
        elif send_strategy == "Один канал":
            ok, raw = send_himchistka_single(phone, msg_text, full_type_value, tags_list, target_source)
        else:
            ok, raw = send_wa_template(phone, wa_template)
    else:
        if send_strategy == "Каскад":
            ok, raw = send_cleaning_hde(phone, msg_text, full_type_value, tags_list, "Каскад", cascade_order=cascade_order)
        else:
            ok, raw = send_cleaning_hde(phone, msg_text, full_type_value, tags_list, "Один канал", source=target_source)
    delivered, detail, channel = parse_response(ok, raw)
    return ok, raw, delivered, detail, channel


# ── ГЛАВНАЯ ОБЛАСТЬ ───────────────────────────────────────────────────────────
unit_badge = "HDE · qlean" if business_unit == "Химчистка" else "HDE · qlean2"
st.markdown("# Оркестратор рассылок")
st.caption(f"Направление: **{business_unit}** ({unit_badge})  ·  Стратегия: **{send_strategy}**")
st.markdown("---")

cascade_blocked = send_strategy == "Каскад" and not cascade_order

tab_single, tab_bulk = st.tabs(["Один номер", "Массовая рассылка"])


# ── ВКЛАДКА: ОДИН НОМЕР ──────────────────────────────────────────────────────
with tab_single:
    st.markdown("Отправка на один номер без загрузки файла.")
    st.markdown("")

    phone_input = st.text_input(
        "Номер телефона",
        placeholder="79001234567",
        max_chars=20,
        key="single_phone"
    )

    if send_strategy in ("Каскад", "Один канал"):
        with st.expander("Предпросмотр сообщения"):
            st.code(msg_text, language=None)
            st.caption(f"type_value: {full_type_value} [XX]  (XX — случайный двузначный суффикс)")

    if cascade_blocked:
        st.warning("Выберите хотя бы один канал в приоритете каскада.")
    else:
        if st.button("ОТПРАВИТЬ", use_container_width=True, key="btn_single"):
            raw_phone = phone_input.strip()
            if not raw_phone:
                st.warning("Введите номер телефона.")
            else:
                with st.spinner("Отправка..."):
                    ok, raw, delivered, detail, channel = dispatch(raw_phone)

                norm        = normalize_phone(raw_phone)
                css_class   = "result-ok" if delivered else "result-fail"
                status_html = '<span class="tag-ok">ДОСТАВЛЕНО</span>' if delivered else '<span class="tag-fail">НЕ ДОСТАВЛЕНО</span>'
                via_line    = f"<br>Канал:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{channel}" if delivered else ""
                reason_line = f"<br>Причина:&nbsp;&nbsp;&nbsp;&nbsp;{detail}" if detail else ""

                st.markdown(
                    f'<div class="result-card {css_class}">'
                    f'Статус:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{status_html}'
                    f'<br>Номер:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{norm}'
                    f'{via_line}{reason_line}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                with st.expander("Сырой ответ"):
                    st.code(raw, language="json")


# ── ВКЛАДКА: МАССОВАЯ РАССЫЛКА ───────────────────────────────────────────────
with tab_bulk:
    st.markdown("Загрузите Excel-файл. Первый столбец — номера телефонов.")
    st.markdown("")

    uploaded_file = st.file_uploader(
        "Файл .xlsx",
        type=["xlsx"],
        label_visibility="collapsed"
    )

    if uploaded_file:
        phones      = []
        parse_error = None
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
            st.markdown("### Параметры запуска")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Получателей",    len(phones))
            c2.metric("Направление",    business_unit)
            c3.metric("Стратегия",      send_strategy)
            est = int(len(phones) * (delay_ms / 1000 + 0.6))
            c4.metric("Оценка времени", f"~{est} сек")

            if send_strategy in ("Каскад", "Один канал"):
                with st.expander("Предпросмотр сообщения"):
                    st.code(msg_text, language=None)
                    st.caption(f"type_value: {full_type_value} [XX]  (XX — случайный двузначный суффикс)")

            st.markdown("---")

            if cascade_blocked:
                st.warning("Выберите хотя бы один канал в приоритете каскада.")

            elif st.button("ЗАПУСТИТЬ РАССЫЛКУ", use_container_width=True, key="btn_bulk"):

                progress_bar = st.progress(0, text="Запуск...")
                log_slot     = st.empty()
                results      = []
                log_lines: list[str] = []
                t_start      = time.time()

                for i, phone in enumerate(phones):
                    norm = normalize_phone(phone)
                    ok, raw, delivered, detail, channel = dispatch(phone)

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

                    done    = i + 1
                    elapsed = time.time() - t_start
                    rate    = done / elapsed if elapsed > 0 else 1
                    eta     = int((len(phones) - done) / rate)
                    progress_bar.progress(
                        done / len(phones),
                        text=f"{done} / {len(phones)}  |  ETA {eta} сек"
                    )

                    results.append({
                        "Телефон":     phone,
                        "Нормализован": norm,
                        "Доставлено":  "Да" if delivered else "Нет",
                        "Канал":       channel,
                        "Детали":      detail,
                        "Raw":         raw[:200],
                    })

                    time.sleep(delay_ms / 1000)

                log_slot.empty()
                progress_bar.empty()

                df          = pd.DataFrame(results)
                total       = len(df)
                delivered_n = (df["Доставлено"] == "Да").sum()
                failed_n    = total - delivered_n
                duration    = int(time.time() - t_start)

                st.markdown("---")
                st.markdown("### Результаты")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Всего",         total)
                m2.metric("Доставлено",    delivered_n, f"{delivered_n / total * 100:.1f}%")
                m3.metric("Не доставлено", failed_n,    f"-{failed_n / total * 100:.1f}%")
                m4.metric("Время",         f"{duration} сек")

                st.markdown("")
                ch_col, err_col = st.columns(2)

                with ch_col:
                    st.markdown("**По каналам**")
                    ch_data = df[df["Доставлено"] == "Да"]["Канал"].value_counts()
                    if not ch_data.empty:
                        st.bar_chart(ch_data)
                    else:
                        st.caption("Нет успешных доставок")

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
                st.dataframe(
                    df[["Телефон", "Нормализован", "Доставлено", "Канал", "Детали"]],
                    use_container_width=True,
                    hide_index=True
                )

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Отчёт")

                fname = f"рассылка_{business_unit.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    "Скачать отчёт (.xlsx)",
                    data=buf.getvalue(),
                    file_name=fname,
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
