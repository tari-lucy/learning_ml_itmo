import streamlit as st
# Workaround: streamlit-cookies-manager использует устаревший st.cache
st.cache = st.cache_data

import re
import requests
import pandas as pd
from datetime import datetime
from streamlit_cookies_manager import EncryptedCookieManager

API_URL = "http://app:8000"

st.set_page_config(page_title="MeetingScribe", page_icon="🎙️", initial_sidebar_state="expanded")

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
    """Информативный парсер ошибок от backend"""
    FIELD_RU = {"email": "Email", "password": "Пароль", "name": "Имя", "amount": "Сумма", "title": "Название"}
    MSG_RU = {
        "String should have at least 4 characters": "должен быть не менее 4 символов",
        "value is not a valid email address": "некорректный формат email",
        "field required": "обязательное поле",
        "Input should be greater than 0": "должно быть больше 0",
    }
    prefix = f"[HTTP {response.status_code}]"
    try:
        data = response.json()
        detail = data.get('detail')
        if isinstance(detail, list):
            items = []
            for e in detail:
                loc = e.get('loc', [])
                field = loc[-1] if loc else ""
                field_ru = FIELD_RU.get(field, field)
                msg = e.get('msg', '')
                msg = msg.replace("Value error, ", "")
                for eng, ru in MSG_RU.items():
                    if eng in msg:
                        msg = ru
                        break
                items.append(f"{field_ru}: {msg}")
            return f"{prefix} " + "; ".join(items)
        if detail:
            return f"{prefix} {detail}"
        return f"{prefix} {data}"
    except Exception:
        pass
    body = (response.text or "").strip()
    return f"{prefix} {body}" if body else prefix


def extract_speakers(text: str) -> list[str]:
    """Находит все уникальные идентификаторы SPEAKER_XX в тексте, в порядке появления."""
    if not text:
        return []
    found = re.findall(r"SPEAKER_\d+", text)
    seen = set()
    unique = []
    for s in found:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def apply_speaker_names(text: str, names: dict) -> str:
    """Заменяет SPEAKER_XX на реальные имена. Пустые имена — оставляет идентификатор как есть."""
    if not text or not names:
        return text
    result = text
    for speaker_id, name in names.items():
        if name and name.strip():
            result = result.replace(speaker_id, name.strip())
    return result


MODEL_LABEL = {"whisper": "🎙️  Whisper", "summary": "📝 Саммари (Deepseek v3.2)", "protocol": "📋 Протокол (Deepseek v3.2)"}
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
    icon = STATUS_ICON.get(t.get("status"), "•")
    date = t.get("created_at", "")[:16].replace("T", " ")
    return f"{icon} {name} · {date}"


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
    st.title("MeetingScribe — AI-секретарь для совещаний")
    st.markdown("""
    Просто загружете аудио с совещания — и получаете:
    - 🎙️ **Транскрипт** с разметкой по спикерам
    - 📝 **Саммари** — краткое резюме встречи
    - 📋 **Протокол** решений и договорённостей

    **Как работает:** оплатили кредиты → загрузили mp3/wav → через пару минут получил результат.
    """)

elif page == "📝 Регистрация":
    st.title("Регистрация")
    with st.form("signup"):
        name = st.text_input("Имя *")
        email = st.text_input("Email *")
        password = st.text_input("Пароль * (минимум 4 символа)", type="password")
        submitted = st.form_submit_button("Зарегистрироваться")

    if submitted:
        if not name or not email or not password:
            st.error("❌ Заполни все поля (отмеченные звёздочкой)")
        else:
            r = requests.post(f"{API_URL}/auth/signup", json={"name": name, "email": email, "password": password})
            if r.status_code == 201:
                st.success("✅ Готово! Теперь зайди через «Вход»")
            else:
                st.error(f"❌ {parse_error(r)}")

elif page == "🔑 Вход":
    st.title("Вход")
    with st.form("signin"):
        email = st.text_input("Email *")
        password = st.text_input("Пароль *", type="password")
        submitted = st.form_submit_button("Войти")

    if submitted:
        if not email or not password:
            st.error("❌ Заполни оба поля")
        else:
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
    st.caption("Минимум 1 кредит, максимум 100 000")
    amount = st.number_input("Сумма пополнения (кредиты)", min_value=1, max_value=100000, value=100, step=10)
    if st.button("Пополнить"):
        if not amount or amount < 1:
            st.error("❌ Сумма должна быть от 1 до 100 000 кредитов")
        else:
            r = requests.post(f"{API_URL}/balance/topup", json={"amount": amount}, headers=auth_headers())
            if r.status_code == 200:
                d = r.json()
                st.success(f"✅ {d['message']}. Новый баланс: **{d['new_balance']:.0f} кр.**")
            else:
                st.error(f"❌ {parse_error(r)}")

elif page == "🎙️ Обработка аудио":
    st.title("Обработка аудио")

    # Загружаем все задачи юзера один раз за рендер
    r_tasks = requests.get(f"{API_URL}/history/predictions", headers=auth_headers())
    tasks = r_tasks.json() if r_tasks.status_code == 200 else []

    tab1, tab2 = st.tabs(["🎙️ Загрузить аудио", "📁 Мои записи"])

    # --- 1. Загрузка нового аудио ---
    with tab1:
        st.caption("Загрузи аудиофайл, чтобы получить транскрипт с разметкой по спикерам. **Стоимость: 10 кредитов**")
        title = st.text_input("Название записи", placeholder="Например: Планёрка 21 апреля", max_chars=200)
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
                    st.info("Перейди во вкладку **«Мои записи»** через минуту.")
                else:
                    st.error(f"❌ {parse_error(r)}")

    # --- 2. Мои записи (всё в одном месте) ---
    with tab2:
        if st.button("🔄 Обновить"):
            st.rerun()

        # Показываем только whisper-задачи как "записи"
        whisper_tasks = [t for t in tasks if t.get("model_name") == "whisper"]

        if not whisper_tasks:
            st.info("Здесь появятся записи после загрузки аудио. Начни с вкладки «Загрузить аудио».")
        else:
            options = {task_label(t): t["id"] for t in reversed(whisper_tasks)}
            label = st.selectbox("Запись", list(options.keys()))
            whisper_id = options[label]

            # Получаем актуальный результат whisper
            r = requests.get(f"{API_URL}/predict/{whisper_id}", headers=auth_headers())
            if r.status_code != 200:
                st.error(f"❌ {parse_error(r)}")
            else:
                d = r.json()
                STATUS_RU = {"done": "готово", "processing": "в обработке", "pending": "в очереди", "error": "ошибка"}
                status_ru = STATUS_RU.get(d['status'], d['status'])
                st.write(f"**Статус транскрибации:** {status_ru}")

                if d['status'] == "pending" or d['status'] == "processing":
                    st.info("⏳ Обработка идёт. Нажми «🔄 Обновить» через минуту.")
                elif d['status'] == "error":
                    st.error("❌ Транскрибация завершилась с ошибкой. Загрузи файл заново.")
                elif d['status'] == "done":
                    names = d.get("speaker_names") or {}

                    # Утилита для отображения артефакта
                    def show_artifact(emoji, title_, key, content, filename, expanded=False, format_speakers=False, names_map=None, owner_task_id=None):
                        if not content:
                            return
                        owner_task_id = owner_task_id or whisper_id
                        display_content = apply_speaker_names(content, names_map or {})
                        download_content = display_content
                        if format_speakers:
                            display_content = re.sub(r'\s*(\[)', r'\n\n\1', display_content).lstrip()
                        with st.expander(f"{emoji} {title_}", expanded=expanded):
                            with st.container(height=400, border=True):
                                st.markdown(display_content)
                            st.download_button(
                                f"⬇️ Скачать {title_.lower()}",
                                data=download_content.encode("utf-8"),
                                file_name=f"{owner_task_id}_{filename}.txt",
                                mime="text/plain",
                                key=f"dl_{owner_task_id}_{key}",
                            )

                    # Транскрипт + диаризация
                    show_artifact("🎙️", "Транскрипт", "transcription", d.get("transcription"), "transcript", expanded=True, names_map=names)
                    show_artifact("👥", "Определение спикеров", "diarization", d.get("diarization"), "diarization", format_speakers=True, names_map=names)

                    # Форма переименования спикеров
                    speakers = extract_speakers(d.get("diarization") or "")
                    if speakers:
                        with st.expander(f"✏️ Переименовать спикеров ({len(speakers)} найдено)", expanded=False):
                            st.caption("Имена применятся к транскрипту, диаризации, и автоматически подтянутся в саммари и протоколы этой записи.")
                            existing = d.get("speaker_names") or {}
                            new_names = {}
                            for sp in speakers:
                                new_names[sp] = st.text_input(sp, value=existing.get(sp, ""), key=f"sp_{whisper_id}_{sp}")
                            if st.button("💾 Сохранить имена", key=f"save_speakers_{whisper_id}"):
                                rr = requests.patch(
                                    f"{API_URL}/predict/{whisper_id}/speakers",
                                    json={"speaker_names": new_names},
                                    headers=auth_headers(),
                                )
                                if rr.status_code == 200:
                                    st.success("✅ Имена сохранены")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {parse_error(rr)}")

                    st.divider()
                    st.subheader("AI-обработка")
                    st.caption("Создай дополнительные артефакты на основе этой записи. **Стоимость: 5 кредитов за каждый.**")

                    # --- Блок саммари ---
                    related_summary = next(
                        (t for t in tasks if t.get("model_name") == "summary" and t.get("input_data") == f"source_task={whisper_id}"),
                        None
                    )

                    if not related_summary:
                        if st.button("📝 Создать саммари", key=f"create_summary_{whisper_id}", use_container_width=True):
                            rr = requests.post(f"{API_URL}/predict/summary", json={"source_task_id": whisper_id}, headers=auth_headers())
                            if rr.status_code == 202:
                                st.success("✅ Задача на саммари принята")
                                st.rerun()
                            else:
                                st.error(f"❌ {parse_error(rr)}")
                    elif related_summary['status'] in ("pending", "processing"):
                        st.info(f"⏳ Саммари в обработке (задача №{related_summary['id']}). Нажми «🔄 Обновить» через минуту.")
                    elif related_summary['status'] == "error":
                        st.error(f"❌ Саммари (задача №{related_summary['id']}): ошибка обработки.")
                        if st.button("🔁 Создать саммари заново", key=f"retry_summary_{whisper_id}"):
                            rr = requests.post(f"{API_URL}/predict/summary", json={"source_task_id": whisper_id}, headers=auth_headers())
                            if rr.status_code == 202:
                                st.success("✅ Новая задача принята")
                                st.rerun()
                            else:
                                st.error(f"❌ {parse_error(rr)}")
                    else:  # done
                        rr = requests.get(f"{API_URL}/predict/{related_summary['id']}", headers=auth_headers())
                        if rr.status_code == 200:
                            sd = rr.json()
                            sd_names = sd.get("speaker_names") or names
                            show_artifact("📝", "Саммари", "summary", sd.get("summary"), "summary", expanded=True, names_map=sd_names, owner_task_id=related_summary['id'])

                    # --- Блок протокола ---
                    related_protocol = next(
                        (t for t in tasks if t.get("model_name") == "protocol" and t.get("input_data") == f"source_task={whisper_id}"),
                        None
                    )

                    if not related_protocol:
                        if st.button("📋 Создать протокол", key=f"create_protocol_{whisper_id}", use_container_width=True):
                            rr = requests.post(f"{API_URL}/predict/protocol", json={"source_task_id": whisper_id}, headers=auth_headers())
                            if rr.status_code == 202:
                                st.success("✅ Задача на протокол принята")
                                st.rerun()
                            else:
                                st.error(f"❌ {parse_error(rr)}")
                    elif related_protocol['status'] in ("pending", "processing"):
                        st.info(f"⏳ Протокол в обработке (задача №{related_protocol['id']}). Нажми «🔄 Обновить» через минуту.")
                    elif related_protocol['status'] == "error":
                        st.error(f"❌ Протокол (задача №{related_protocol['id']}): ошибка обработки.")
                        if st.button("🔁 Создать протокол заново", key=f"retry_protocol_{whisper_id}"):
                            rr = requests.post(f"{API_URL}/predict/protocol", json={"source_task_id": whisper_id}, headers=auth_headers())
                            if rr.status_code == 202:
                                st.success("✅ Новая задача принята")
                                st.rerun()
                            else:
                                st.error(f"❌ {parse_error(rr)}")
                    else:  # done
                        rr = requests.get(f"{API_URL}/predict/{related_protocol['id']}", headers=auth_headers())
                        if rr.status_code == 200:
                            pd_ = rr.json()
                            pd_names = pd_.get("speaker_names") or names
                            show_artifact("📋", "Протокол", "protocol", pd_.get("protocol"), "protocol", expanded=False, names_map=pd_names, owner_task_id=related_protocol['id'])

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
                        "Модель": MODEL_LABEL.get(t.get("model_name"), t.get("model_name")),
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
