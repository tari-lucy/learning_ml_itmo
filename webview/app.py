import streamlit as st
# Workaround: streamlit-cookies-manager использует устаревший st.cache
st.cache = st.cache_data

import requests
import pandas as pd
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

API_URL = "http://app:8000"

st.set_page_config(page_title="MeetingScribe", page_icon="🎙️")

# --- Cookies manager ---
cookies = EncryptedCookieManager(
    prefix="meetingscribe/",
    password="meeting-scribe-cookie-key-2026"
)
if not cookies.ready():
    st.spinner("Загрузка...")
    st.stop()

# --- Инициализация session state ---
if "token" not in st.session_state:
    st.session_state.token = cookies.get("auth_token") or None
    st.session_state.user_id = int(cookies["auth_user_id"]) if cookies.get("auth_user_id") else None
    st.session_state.email = cookies.get("auth_email") or None
    st.session_state.name = cookies.get("auth_name") or None
    st.session_state.role = cookies.get("auth_role") or None


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def parse_error(response):
    """Безопасный парсер ошибок от backend"""
    try:
        return response.json().get('detail', response.text)
    except Exception:
        return (response.text or f"HTTP {response.status_code}")[:300]


MODEL_LABEL = {"whisper": "🎙️ транскрибация", "summary": "📝 саммари"}
STATUS_ICON = {"done": "✅", "error": "❌", "pending": "⏳", "processing": "⚙️"}
STATUS_TEXT = {"done": "✅ Готово", "processing": "⚙️ В обработке", "pending": "⏳ В очереди", "error": "❌ Ошибка"}
TRANSACTION_TYPE = {
    "credit": "💰 Пополнение",
    "debit": "➖ Списание",
}


def format_dt(iso_str: str) -> str:
    """ISO datetime → ДД.ММ.ГГ ЧЧ:ММ:СС"""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%y %H:%M:%S")
    except Exception:
        return iso_str[:16].replace("T", " ")


def task_label(t: dict) -> str:
    """Человеческая метка задачи для селектбокса"""
    name = t.get("title") or f"Без названия #{t['id']}"
    model = MODEL_LABEL.get(t.get("model_name", ""), t.get("model_name", ""))
    icon = STATUS_ICON.get(t.get("status"), "•")
    date = t.get("created_at", "")[:16].replace("T", " ")
    return f"{icon} {name} · {model} · {date}"


def login(access_token, user_id, email, name, role):
    st.session_state.token = access_token
    st.session_state.user_id = user_id
    st.session_state.email = email
    st.session_state.name = name
    st.session_state.role = role
    cookies["auth_token"] = access_token
    cookies["auth_user_id"] = str(user_id)
    cookies["auth_email"] = email
    cookies["auth_name"] = name
    cookies["auth_role"] = role
    cookies.save()


def logout():
    for key in ["token", "user_id", "email", "role"]:
        st.session_state[key] = None
    for ck in ["auth_token", "auth_user_id", "auth_email", "auth_name", "auth_role"]:
        if ck in cookies:
            del cookies[ck]
    cookies.save()


def go_to_topup():
    st.session_state.nav_radio = "💰 Пополнить"


# --- Sidebar ---
st.sidebar.title("🎙️ MeetingScribe")

if st.session_state.token:
    st.sidebar.markdown(f"### 👋 Привет, {st.session_state.name}")
    r_bal = requests.get(f"{API_URL}/balance/", headers=auth_headers())
    if r_bal.status_code == 200:
        st.sidebar.markdown(f"**💰 Баланс:** {r_bal.json()['balance']:.0f} кр.")
    page = st.sidebar.radio(
        "Меню",
        ["🏠 Главная", "👤 Кабинет", "💰 Пополнить", "🎙️ Обработка аудио", "📜 История"],
        key="nav_radio",
    )
    if st.sidebar.button("Выйти"):
        logout()
        st.rerun()
else:
    page = st.sidebar.radio("Меню", ["🏠 Главная", "📝 Регистрация", "🔑 Вход"])


# --- Страницы ---
if page == "🏠 Главная":
    st.title("MeetingScribe — AI-секретарь совещаний")
    st.markdown("""
    Загружай аудио совещаний — получай:
    - 🎙️ **Транскрипт** с разметкой по спикерам
    - 📝 **Саммари** — краткое резюме встречи
    - 📋 **Протокол** решений и договорённостей

    **Как работает:** оплатил кредиты → загрузил mp3/wav → через пару минут получил результат.
    """)

elif page == "📝 Регистрация":
    st.title("Регистрация")
    with st.form("signup"):
        name = st.text_input("Имя")
        email = st.text_input("Email")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Зарегистрироваться")

    if submitted:
        r = requests.post(f"{API_URL}/auth/signup", json={"name": name, "email": email, "password": password})
        if r.status_code == 201:
            st.success("✅ Готово! Теперь зайди через «Вход»")
        else:
            st.error(f"❌ {parse_error(r)}")

elif page == "🔑 Вход":
    st.title("Вход")
    with st.form("signin"):
        email = st.text_input("Email")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти")

    if submitted:
        r = requests.post(f"{API_URL}/auth/signin", data={"username": email, "password": password})
        if r.status_code == 200:
            data = r.json()
            login(data["access_token"], data["user_id"], email, data["name"], data["role"])
            st.success("✅ Вход выполнен")
            st.rerun()
        else:
            st.error(f"❌ {parse_error(r)}")

elif page == "👤 Кабинет":
    st.title("Личный кабинет")
    r = requests.get(f"{API_URL}/balance/", headers=auth_headers())
    if r.status_code == 200:
        b = r.json()
        role_ru = {"user": "пользователь", "admin": "администратор"}.get(st.session_state.role, st.session_state.role)
        st.markdown(f"""
**Имя:** {st.session_state.name}

**Email:** {st.session_state.email}

**Роль:** {role_ru}

**Баланс:** {b['balance']:.0f} кр.
""")
        st.button("💰 Пополнить баланс", on_click=go_to_topup)
    else:
        st.error("Не удалось получить баланс")

elif page == "💰 Пополнить":
    st.title("Пополнить баланс")
    amount = st.number_input("Сумма пополнения (кредиты)", min_value=1, value=100, step=10)
    if st.button("Пополнить"):
        r = requests.post(f"{API_URL}/balance/topup", json={"amount": amount}, headers=auth_headers())
        if r.status_code == 200:
            d = r.json()
            st.success(f"✅ {d['message']}. Новый баланс: **{d['new_balance']:.0f} кр.**")
        else:
            st.error(f"❌ {parse_error(r)}")

elif page == "🎙️ Обработка аудио":
    st.title("Обработка аудио")

    # Загружаем задачи юзера один раз за рендер
    r_tasks = requests.get(f"{API_URL}/history/predictions", headers=auth_headers())
    tasks = r_tasks.json() if r_tasks.status_code == 200 else []

    tab1, tab2, tab3 = st.tabs(["🎙️ Транскрибация", "📝 Саммари", "📁 Мои записи"])

    # --- 1. Транскрибация ---
    with tab1:
        st.caption("Загрузи аудио → получишь транскрипт с разметкой по спикерам. **Стоимость: 10 кр.**")
        title = st.text_input("Название записи", placeholder="Например: Планёрка 21 апреля")
        audio = st.file_uploader("Аудиофайл", type=["mp3", "wav", "m4a", "ogg", "flac", "webm"])
        if st.button("Отправить на транскрибацию", key="whisper_btn"):
            if not audio:
                st.warning("Сначала выбери файл")
            else:
                files = {"audio": (audio.name, audio.getvalue(), audio.type)}
                r = requests.post(
                    f"{API_URL}/predict/whisper",
                    files=files,
                    data={"title": title},
                    headers=auth_headers(),
                )
                if r.status_code == 202:
                    d = r.json()
                    st.session_state.last_task_id = d["task_id"]
                    st.success(f"✅ Задача №**{d['task_id']}** принята. Списано **{d['credits_charged']} кр.**")
                    st.info("Проверь результат во вкладке **«Мои записи»** через минуту.")
                else:
                    st.error(f"❌ {parse_error(r)}")

    # --- 2. Саммари ---
    with tab2:
        st.caption("Создай саммари из готового транскрипта. **Стоимость: 5 кр.**")
        whisper_done = [t for t in tasks if t.get("model_name") == "whisper" and t.get("status") == "done"]
        if not whisper_done:
            st.info("Пока нет готовых транскрипций. Сначала обработай аудио во вкладке «Транскрибация».")
        else:
            options = {task_label(t): t["id"] for t in reversed(whisper_done)}
            label = st.selectbox("Выбери транскрипцию", list(options.keys()))
            if st.button("Создать саммари", key="summary_btn"):
                r = requests.post(
                    f"{API_URL}/predict/summary",
                    json={"source_task_id": options[label]},
                    headers=auth_headers(),
                )
                if r.status_code == 202:
                    d = r.json()
                    st.success(f"✅ Задача №**{d['task_id']}** принята. Списано **{d['credits_charged']} кр.**")
                else:
                    st.error(f"❌ {parse_error(r)}")

    # --- 3. Мои записи ---
    with tab3:
        if st.button("🔄 Обновить список"):
            st.rerun()

        if not tasks:
            st.info("Здесь появятся твои записи после запуска транскрибации или саммари. Начни с вкладки «Транскрибация».")
        else:
            options = {task_label(t): t["id"] for t in reversed(tasks)}
            label = st.selectbox("Запись", list(options.keys()))
            task_id = options[label]

            r = requests.get(f"{API_URL}/predict/{task_id}", headers=auth_headers())
            if r.status_code == 200:
                d = r.json()
                STATUS_RU = {"done": "готово", "processing": "в обработке", "pending": "в очереди", "error": "ошибка"}
                status_ru = STATUS_RU.get(d['status'], d['status'])
                model_ru = MODEL_LABEL.get(d['model_name'], d['model_name'])
                st.write(f"**Статус:** {status_ru} · **Модель:** {model_ru}")

                def show_result(emoji, title_, key, content, filename, expanded=False):
                    if not content:
                        return
                    with st.expander(f"{emoji} {title_}", expanded=expanded):
                        with st.container(height=400, border=True):
                            st.markdown(content)
                        st.download_button(
                            f"⬇️ Скачать {title_.lower()}",
                            data=content.encode("utf-8"),
                            file_name=f"{task_id}_{filename}.txt",
                            mime="text/plain",
                            key=f"dl_{task_id}_{key}",
                        )

                show_result("🎙️", "Транскрипт", "transcription", d.get("transcription"), "transcript", expanded=True)
                show_result("👥", "Диаризация", "diarization", d.get("diarization"), "diarization")
                show_result("📋", "Протокол", "protocol", d.get("protocol"), "protocol")
                show_result("📝", "Саммари", "summary", d.get("summary"), "summary", expanded=True)
            else:
                st.error(f"❌ {parse_error(r)}")

elif page == "📜 История":
    st.title("История операций")
    tab1, tab2 = st.tabs(["🤖 ML-запросы", "💳 Транзакции"])

    with tab1:
        r = requests.get(f"{API_URL}/history/predictions", headers=auth_headers())
        if r.status_code == 200:
            data = r.json()
            if data:
                df = pd.DataFrame([
                    {
                        "Название": t.get("title") or f"Без названия #{t['id']}",
                        "Тип": MODEL_LABEL.get(t.get("model_name"), t.get("model_name")),
                        "Статус": STATUS_TEXT.get(t.get("status"), t.get("status")),
                        "Дата и время": format_dt(t.get("created_at", "")),
                    }
                    for t in reversed(data)
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Ещё нет ML-запросов")
        else:
            st.error(f"Ошибка: {parse_error(r)}")

    with tab2:
        r = requests.get(f"{API_URL}/history/transactions", headers=auth_headers())
        if r.status_code == 200:
            data = r.json()
            if data:
                df = pd.DataFrame([
                    {
                        "Дата и время": format_dt(t.get("created_at", "")),
                        "Операция": TRANSACTION_TYPE.get(t.get("type"), t.get("type")),
                        "Сумма, кредиты": t.get("amount", 0),
                        "Связанная задача": t.get("task_id") or "—",
                    }
                    for t in reversed(data)
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Ещё нет транзакций")
        else:
            st.error(f"Ошибка: {parse_error(r)}")
