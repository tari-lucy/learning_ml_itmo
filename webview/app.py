import streamlit as st
import requests

API_URL = "http://app:8000"

# --- Инициализация state ---
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.user_id = None
    st.session_state.email = None
    st.session_state.role = None


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def logout():
    for key in ["token", "user_id", "email", "role"]:
        st.session_state[key] = None


# --- Sidebar ---
st.sidebar.title("🎙️  MeetingScribe")

if st.session_state.token:
    st.sidebar.success(f"✅ {st.session_state.email}")
    page = st.sidebar.radio("Меню", ["🏠 Главная", "👤 Кабинет", "💰 Пополнить", "🎙️  Обработка аудио", "📜 История"])
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
    - 🎙️  **Транскрипт** с разметкой по спикерам
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
            st.error(f"❌ {r.json().get('detail', r.text)}")

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
            st.session_state.token = data["access_token"]
            st.session_state.user_id = data["user_id"]
            st.session_state.email = email
            st.session_state.role = data["role"]
            st.success("✅ Вход выполнен")
            st.rerun()
        else:
            st.error(f"❌ {r.json().get('detail', r.text)}")

elif page == "👤 Кабинет":
    st.title("Личный кабинет")
    r = requests.get(f"{API_URL}/balance/", headers=auth_headers())
    if r.status_code == 200:
        b = r.json()
        col1, col2, col3 = st.columns(3)
        col1.metric("Баланс", f"{b['balance']:.0f} кр.")
        col2.metric("Email", st.session_state.email)
        col3.metric("Роль", st.session_state.role)
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
            st.error(f"❌ {r.json().get('detail', r.text)}")

elif page == "🎙️  Обработка аудио":
    st.title("Обработка аудио")

    # Загружаем задачи юзера один раз за рендер
    r_tasks = requests.get(f"{API_URL}/history/predictions", headers=auth_headers())
    tasks = r_tasks.json() if r_tasks.status_code == 200 else []

    tab1, tab2, tab3 = st.tabs(["🎙️  Транскрибация", "📝 Саммари", "📂 Мои задачи"])

    # --- 1. Транскрибация ---
    with tab1:
        st.caption("Загрузи аудио → получишь транскрипт с разметкой по спикерам. **Стоимость: 10 кр.**")
        audio = st.file_uploader("Аудиофайл", type=["mp3", "wav", "m4a", "ogg", "flac", "webm"])
        if st.button("Отправить на транскрибацию", key="whisper_btn"):
            if not audio:
                st.warning("Сначала выбери файл")
            else:
                files = {"audio": (audio.name, audio.getvalue(), audio.type)}
                r = requests.post(f"{API_URL}/predict/whisper", files=files, headers=auth_headers())
                if r.status_code == 202:
                    d = r.json()
                    st.session_state.last_task_id = d["task_id"]
                    st.success(f"✅ Задача №**{d['task_id']}** принята. Списано **{d['credits_charged']} кр.**")
                    st.info("Проверь результат во вкладке **«Мои задачи»** через минуту.")
                else:
                    st.error(f"❌ {r.json().get('detail', r.text)}")

    # --- 2. Саммари ---
    with tab2:
        st.caption("Создай саммари из готового транскрипта. **Стоимость: 5 кр.**")
        whisper_done = [t for t in tasks if t.get("model_name") == "whisper" and t.get("status") == "done"]

        if not whisper_done:
            st.info("Пока нет готовых транскрипций. Сначала обработай аудио во вкладке «Транскрибация».")
        else:
            options = {f"#{t['id']} · {t['created_at'][:16].replace('T', ' ')}": t["id"] for t in reversed(whisper_done)}
            label = st.selectbox("Выбери транскрипцию", list(options.keys()))
            if st.button("Создать саммари", key="summary_btn"):
                r = requests.post(f"{API_URL}/predict/summary", json={"source_task_id": options[label]}, headers=auth_headers())
                if r.status_code == 202:
                    d = r.json()
                    st.success(f"✅ Задача №**{d['task_id']}** принята. Списано **{d['credits_charged']} кр.**")
                else:
                    st.error(f"❌ {r.json().get('detail', r.text)}")

    # --- 3. Мои задачи ---
    with tab3:
        if not tasks:
            st.info("Пока нет задач. Начни с «Транскрибации».")
        else:
            if st.button("🔄 Обновить список"):
                st.rerun()

            status_icon = {"done": "✅", "error": "❌", "pending": "⏳", "processing": "⚙️ "}
            options = {
                f"{status_icon.get(t.get('status'), '•')} #{t['id']} · {t['model_name']} · {t['created_at'][:16].replace('T', '')}": t["id"]
                for t in reversed(tasks)
            }
            label = st.selectbox("Задача", list(options.keys()))
            task_id = options[label]

            r = requests.get(f"{API_URL}/predict/{task_id}", headers=auth_headers())
            if r.status_code == 200:
                d = r.json()
                st.write(f"**Статус:** `{d['status']}` | **Модель:** `{d['model_name']}`")

                if d.get("transcription"):
                    with st.expander("🎙️  Транскрипт", expanded=True):
                        st.text(d["transcription"])
                if d.get("diarization"):
                    with st.expander("👥 Диаризация"):
                        st.text(d["diarization"])
                if d.get("protocol"):
                    with st.expander("📋 Протокол"):
                        st.text(d["protocol"])
                if d.get("summary"):
                    with st.expander("📝 Саммари", expanded=True):
                        st.text(d["summary"])
            else:
                st.error(f"❌ {r.json().get('detail', r.text)}")

elif page == "📜 История":
    st.title("История операций")
    tab1, tab2 = st.tabs(["🤖 ML-запросы", "💳 Транзакции"])

    with tab1:
        r = requests.get(f"{API_URL}/history/predictions", headers=auth_headers())
        if r.status_code == 200:
            data = r.json()
            if data:
                st.dataframe(data, use_container_width=True)
            else:
                st.info("Ещё нет ML-запросов")
        else:
            st.error(f"Ошибка: {r.text}")

    with tab2:
        r = requests.get(f"{API_URL}/history/transactions", headers=auth_headers())
        if r.status_code == 200:
            data = r.json()
            if data:
                st.dataframe(data, use_container_width=True)
            else:
                st.info("Ещё нет транзакций")
        else:
            st.error(f"Ошибка: {r.text}")
