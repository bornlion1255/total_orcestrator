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
    page_title="D2C · Orchestrator",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── DARK TECH THEME ───────────────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background: #0D1117; color: #E6EDF3; }

[data-testid="stSidebar"] {
    background: #161B22;
    border-right: 1px solid #30363D;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div { color: #E6EDF3 !important; }

.stTextInput > div > div > input,
.stTextArea  > div > div > textarea {
    background: #21262D !important;
    border: 1px solid #30363D !important;
    color: #E6EDF3 !important;
    border-radius: 6px !important;
    font-size: 13px !important;
}
.stSelectbox   > div > div,
.stMultiSelect > div > div {
    background: #21262D !important;
    border: 1px solid #30363D !important;
    color: #E6EDF3 !important;
}

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

.stProgress > div > div > div { background: #58A6FF !important; }

[data-testid="metric-container"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    padding: 16px !important;
}

[data-testid="stFileUploader"] {
    background: #161B22 !important;
    border: 1px dashed #30363D !important;
    border-radius: 8px !important;
}

[data-testid="stDataFrame"] {
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* Tabs */
.stTabs [data-testid="stTabBar"] {
    background: #161B22;
    border-bottom: 1px solid #30363D;
    border-radius: 8px 8px 0 0;
}
.stTabs [data-testid="stTabBar"] button {
    color: #8B949E !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 20px !important;
}
.stTabs [data-testid="stTabBar"] button[aria-selected="true"] {
    color: #E6EDF3 !important;
    border-bottom: 2px solid #58A6FF !important;
}
.stTabs [data-testid="stTabPanel"] {
    background: #0D1117;
    border: 1px solid #30363D;
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 24px !important;
}

hr { border-color: #30363D !important; margin: 12px 0 !important; }
details summary { color: #8B949E !important; font-size: 13px !important; }
#MainMenu, footer { visibility: hidden !important; }
header[data-testid="stHeader"] {
    background: #0D1117 !important;
    border-bottom: 1px solid #30363D;
}

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

.result-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 20px 24px;
    margin-top: 16px;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
}
.result-ok   { border-left: 3px solid #3FB950; }
.result-fail { border-left: 3px solid #F85149; }
.tag-ok   { color: #3FB950; font-weight: 700; }
.tag-fail { color: #F85149; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ── AUTH ──────────────────────────────────────────────────────────────────────
def check_password() -> bool:
    if "APP_PASSWORD" not in st.secrets:
        return True
    if st.session_state.get("authed"):
        return True
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("## D2C · Broadcast Orchestrator")
        pw = st.text_input("Password", type="password", key="pw_input")
        if st.button("Sign in", use_container_width=True):
            if pw == st.secrets["APP_PASSWORD"]:
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
    return False

if not check_password():
    st.stop()


# ── SECRETS ───────────────────────────────────────────────────────────────────
try:
    WA_TOKEN            = st.secrets["WA_TOKEN"]
    WA_INSTANCE_ID      = st.secrets["WA_INSTANCE_ID"]
    YANDEX_CASCADE_URL  = st.secrets["YANDEX_CASCADE_URL"]
    YANDEX_SINGLE_URL   = st.secrets["YANDEX_SINGLE_URL"]
    YANDEX_CLEANING_URL = st.secrets["YANDEX_CLEANING_URL"]
except KeyError as e:
    st.error(f"Missing secret: {e} — check .streamlit/secrets.toml")
    st.stop()

WA_API_URL   = f"https://api.1msg.io/{WA_INSTANCE_ID}/sendTemplate?token={WA_TOKEN}"
WA_NAMESPACE = "49276b64_15e7_414d_8f35_6ab04bcaa5b1"

CHANNEL_LABELS = {"max": "MAX", "tlgrm": "Telegram", "chat": "In-App Chat"}


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## D2C · Orchestrator")
    st.caption(datetime.now().strftime("%d %b %Y  %H:%M"))
    st.markdown("---")

    st.markdown("**Business unit**")
    business_unit = st.radio(
        "unit",
        ["Химчистка", "Клининг"],
        label_visibility="collapsed",
        help="Химчистка → HDE qlean  |  Клининг → HDE qlean2"
    )

    st.markdown("---")
    st.markdown("**Strategy**")
    send_strategy = st.selectbox(
        "strategy",
        ["Cascade", "Single channel", "WhatsApp Template"],
        label_visibility="collapsed",
        help=(
            "Cascade — пробует каналы по порядку, первый найденный побеждает\n"
            "Single channel — только один указанный канал\n"
            "WhatsApp Template — прямая отправка одобренного шаблона"
        )
    )

    st.markdown("---")

    # Default values
    cascade_order   = []
    target_source   = "chat"
    wa_template     = ""
    msg_text        = ""
    full_type_value = ""
    tags_list       = []

    if send_strategy in ("Cascade", "Single channel"):
        default_subject = "Клининг" if business_unit == "Клининг" else "Забытые вещи"
        subject = st.text_input(
            "Subject",
            value=default_subject,
            help="Подставляется в type_value: Рассылка: <subject> [XX]"
        )
        full_type_value = f"Рассылка: {subject}"

        msg_text = st.text_area("Message", value="Текст сообщения...", height=110)

        default_tags = "рассылка,клининг" if business_unit == "Клининг" else "рассылка"
        tags_raw  = st.text_input("Tags (comma-separated)", value=default_tags)
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]

        if send_strategy == "Cascade":
            default_order = ["max", "tlgrm"] if business_unit == "Клининг" else ["chat", "tlgrm", "max"]
            cascade_order = st.multiselect(
                "Channel priority (left = first)",
                options=["max", "tlgrm", "chat"],
                default=default_order,
                format_func=lambda x: CHANNEL_LABELS[x]
            )
        else:
            target_source = st.selectbox(
                "Channel",
                ["chat", "tlgrm", "max"],
                format_func=lambda x: CHANNEL_LABELS[x]
            )

    else:  # WhatsApp Template
        wa_template = st.text_input(
            "Template name",
            value="poteri",
            help="Шаблон должен быть одобрен в 1msg"
        )

    st.markdown("---")
    delay_ms = st.slider("Delay between sends (ms)", 100, 2000, 200, step=50)


# ── SEND FUNCTIONS ────────────────────────────────────────────────────────────
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
    payload["target_sources" if strategy == "Cascade" else "target_source"] = (
        cascade_order if strategy == "Cascade" else source
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
    """Returns (delivered, detail, channel)"""
    if not ok:
        return False, raw[:120], "—"
    try:
        body = json.loads(raw)
        delivered = body.get("status") == "success"
        return delivered, body.get("detail", ""), body.get("delivered_via", "—")
    except Exception:
        if "sent" in raw.lower():
            return True, "WA delivered", "whatsapp"
        return True, "200 OK", "—"

def dispatch(phone: str) -> tuple[bool, str, bool, str, str]:
    """Routes one phone through the selected strategy. Returns (ok, raw, delivered, detail, channel)."""
    if business_unit == "Химчистка":
        if send_strategy == "Cascade":
            ok, raw = send_himchistka_cascade(phone, msg_text, full_type_value, tags_list, cascade_order)
        elif send_strategy == "Single channel":
            ok, raw = send_himchistka_single(phone, msg_text, full_type_value, tags_list, target_source)
        else:
            ok, raw = send_wa_template(phone, wa_template)
    else:
        if send_strategy == "Cascade":
            ok, raw = send_cleaning_hde(phone, msg_text, full_type_value, tags_list, "Cascade", cascade_order=cascade_order)
        elif send_strategy == "Single channel":
            ok, raw = send_cleaning_hde(phone, msg_text, full_type_value, tags_list, "Single channel", source=target_source)
        else:
            ok, raw = send_wa_template(phone, wa_template)
    delivered, detail, channel = parse_response(ok, raw)
    return ok, raw, delivered, detail, channel


# ── MAIN ─────────────────────────────────────────────────────────────────────
unit_badge = "HDE · qlean" if business_unit == "Химчистка" else "HDE · qlean2"
st.markdown("# Broadcast Orchestrator")
st.caption(f"Unit: **{business_unit}** ({unit_badge})  ·  Strategy: **{send_strategy}**")
st.markdown("---")

cascade_blocked = send_strategy == "Cascade" and not cascade_order

tab_single, tab_bulk = st.tabs(["Single number", "Bulk (Excel)"])


# ── TAB: SINGLE NUMBER ────────────────────────────────────────────────────────
with tab_single:
    st.markdown("Send to one phone number without uploading a file.")
    st.markdown("")

    phone_input = st.text_input(
        "Phone number",
        placeholder="79001234567",
        max_chars=20,
        key="single_phone"
    )

    if send_strategy in ("Cascade", "Single channel"):
        with st.expander("Message preview"):
            st.code(msg_text, language=None)
            st.caption(f"type_value: {full_type_value} [XX]  (XX = random 2-digit suffix)")

    if cascade_blocked:
        st.warning("Select at least one channel in the sidebar cascade order.")
    else:
        if st.button("SEND", use_container_width=True, key="btn_single"):
            raw_phone = phone_input.strip()
            if not raw_phone:
                st.warning("Enter a phone number.")
            else:
                with st.spinner("Sending..."):
                    ok, raw, delivered, detail, channel = dispatch(raw_phone)

                norm = normalize_phone(raw_phone)
                status_class = "result-ok" if delivered else "result-fail"
                status_tag   = '<span class="tag-ok">DELIVERED</span>' if delivered else '<span class="tag-fail">NOT DELIVERED</span>'
                via_line     = f"<br>Channel:&nbsp;&nbsp;&nbsp;{channel}" if delivered else ""
                reason_line  = f"<br>Reason:&nbsp;&nbsp;&nbsp;&nbsp;{detail}" if detail else ""

                st.markdown(
                    f'<div class="result-card {status_class}">'
                    f'Status:&nbsp;&nbsp;&nbsp;&nbsp;{status_tag}'
                    f'<br>Phone:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{norm}'
                    f'{via_line}{reason_line}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                with st.expander("Raw response"):
                    st.code(raw, language="json")


# ── TAB: BULK ────────────────────────────────────────────────────────────────
with tab_bulk:
    st.markdown("Upload an Excel file. First column must contain phone numbers.")
    st.markdown("")

    uploaded_file = st.file_uploader(
        "Drop .xlsx file here",
        type=["xlsx"],
        label_visibility="collapsed"
    )

    if uploaded_file:
        phones = []
        parse_error = None
        try:
            df_input = pd.read_excel(uploaded_file, header=None)
            phones   = df_input.iloc[:, 0].dropna().astype(str).tolist()
            phones   = [p for p in phones if re.search(r'\d', p)]
        except Exception as e:
            parse_error = str(e)

        if parse_error:
            st.error(f"Failed to parse file: {parse_error}")

        elif not phones:
            st.warning("No valid phone numbers found in the file.")

        else:
            # Pre-flight
            st.markdown("### Pre-flight")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Recipients",   len(phones))
            c2.metric("Unit",         business_unit)
            c3.metric("Strategy",     send_strategy)
            est = int(len(phones) * (delay_ms / 1000 + 0.6))
            c4.metric("Est. duration", f"~{est}s")

            if send_strategy in ("Cascade", "Single channel"):
                with st.expander("Message preview"):
                    st.code(msg_text, language=None)
                    st.caption(f"type_value: {full_type_value} [XX]  (XX = random 2-digit suffix)")

            st.markdown("---")

            if cascade_blocked:
                st.warning("Select at least one channel in the sidebar cascade order.")

            elif st.button("LAUNCH BROADCAST", use_container_width=True, key="btn_bulk"):

                progress_bar = st.progress(0, text="Starting...")
                log_slot     = st.empty()
                results      = []
                log_lines: list[str] = []
                t_start      = time.time()

                for i, phone in enumerate(phones):
                    norm = normalize_phone(phone)
                    ok, raw, delivered, detail, channel = dispatch(phone)

                    # Live log
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

                    # Progress + ETA
                    done    = i + 1
                    elapsed = time.time() - t_start
                    rate    = done / elapsed if elapsed > 0 else 1
                    eta     = int((len(phones) - done) / rate)
                    progress_bar.progress(
                        done / len(phones),
                        text=f"{done} / {len(phones)}  |  ETA {eta}s"
                    )

                    results.append({
                        "Phone":      phone,
                        "Normalized": norm,
                        "Delivered":  "Yes" if delivered else "No",
                        "Channel":    channel,
                        "Detail":     detail,
                        "Raw":        raw[:200],
                    })

                    time.sleep(delay_ms / 1000)

                log_slot.empty()
                progress_bar.empty()

                # Results
                df         = pd.DataFrame(results)
                total      = len(df)
                delivered_n = (df["Delivered"] == "Yes").sum()
                failed_n   = total - delivered_n
                duration   = int(time.time() - t_start)

                st.markdown("---")
                st.markdown("### Results")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total",      total)
                m2.metric("Delivered",  delivered_n, f"{delivered_n / total * 100:.1f}%")
                m3.metric("Failed",     failed_n,    f"-{failed_n / total * 100:.1f}%")
                m4.metric("Duration",   f"{duration}s")

                st.markdown("")
                ch_col, err_col = st.columns(2)

                with ch_col:
                    st.markdown("**Delivery by channel**")
                    ch_data = df[df["Delivered"] == "Yes"]["Channel"].value_counts()
                    if not ch_data.empty:
                        st.bar_chart(ch_data)
                    else:
                        st.caption("No successful deliveries")

                with err_col:
                    st.markdown("**Top failure reasons**")
                    failed_df = df[df["Delivered"] == "No"]
                    if not failed_df.empty:
                        reasons = failed_df["Detail"].value_counts().reset_index()
                        reasons.columns = ["Reason", "Count"]
                        st.dataframe(reasons, use_container_width=True, hide_index=True)
                    else:
                        st.success("No failures")

                st.markdown("---")
                st.markdown("**Full report**")
                st.dataframe(
                    df[["Phone", "Normalized", "Delivered", "Channel", "Detail"]],
                    use_container_width=True,
                    hide_index=True
                )

                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                    df.to_excel(writer, index=False, sheet_name="Broadcast Report")

                fname = f"broadcast_{business_unit.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    "Download report (.xlsx)",
                    data=buf.getvalue(),
                    file_name=fname,
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )
