import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client


st.set_page_config(
    page_title="Трекер настроения",
    page_icon="🙂",
    layout="centered"
)


TABLE_NAME = "mood_entries"

today_date = datetime.now().date()


MOOD_OPTIONS = {
    "🙂 Хороший": "+",
    "😐 Обычный": "0",
    "🙁 Плохой": "-"
}

MOOD_NAMES = {
    "+": "🙂 Хороший",
    "0": "😐 Обычный",
    "-": "🙁 Плохой"
}

MOOD_SCORES = {
    "+": 1,
    "0": 0,
    "-": -1
}


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("Трекер настроения")
    st.write("Введи пароль, чтобы открыть приложение.")

    password = st.text_input("Пароль", type="password")

    if st.button("Войти", type="primary", use_container_width=True):
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Неверный пароль.")

    return False


@st.cache_resource
def get_supabase_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]

    return create_client(url, key)


def read_entries():
    supabase = get_supabase_client()

    response = (
        supabase
        .table(TABLE_NAME)
        .select("*")
        .order("date")
        .execute()
    )

    data = response.data

    if not data:
        return pd.DataFrame(columns=["id", "date", "mood", "score", "note", "created_at"])

    df = pd.DataFrame(data)

    for column in ["id", "date", "mood", "score", "note", "created_at"]:
        if column not in df.columns:
            df[column] = ""

    df["date"] = df["date"].astype(str)
    df["mood"] = df["mood"].astype(str)
    df["note"] = df["note"].fillna("").astype(str)

    df = df[df["mood"].isin(MOOD_SCORES.keys())]
    df["score"] = df["mood"].map(MOOD_SCORES)

    return df[["id", "date", "mood", "score", "note", "created_at"]]


def get_entry_for_date(entry_date):
    df = read_entries()
    rows = df[df["date"] == entry_date]

    if len(rows) == 0:
        return None

    return rows.iloc[-1]


def save_entry(entry_date, mood, note):
    supabase = get_supabase_client()

    entry = {
        "date": entry_date,
        "mood": mood,
        "score": MOOD_SCORES[mood],
        "note": note.strip()
    }

    (
        supabase
        .table(TABLE_NAME)
        .upsert(entry, on_conflict="date")
        .execute()
    )


def delete_entry(entry_date):
    supabase = get_supabase_client()

    (
        supabase
        .table(TABLE_NAME)
        .delete()
        .eq("date", entry_date)
        .execute()
    )


def show_entry_page():
    st.subheader("Запись настроения")

    selected_date = st.date_input(
        "Дата записи:",
        value=today_date,
        max_value=today_date
    )

    selected_date_str = selected_date.strftime("%Y-%m-%d")

    existing_entry = get_entry_for_date(selected_date_str)

    option_labels = list(MOOD_OPTIONS.keys())
    default_index = 1
    default_note = ""

    if existing_entry is not None:
        current_mood = existing_entry["mood"]
        default_note = existing_entry["note"]

        current_label = None

        for label, value in MOOD_OPTIONS.items():
            if value == current_mood:
                current_label = label

        if current_label in option_labels:
            default_index = option_labels.index(current_label)

        st.info(
            f"За выбранную дату уже записано: {MOOD_NAMES[current_mood]}. "
            f"Можно обновить запись."
        )

    selected_mood_label = st.radio(
        "Выбери настроение:",
        option_labels,
        index=default_index,
        horizontal=True,
        key=f"mood_{selected_date_str}"
    )

    note = st.text_area(
        "Заметка о дне:",
        value=default_note,
        placeholder="Например: хорошо поработал, устал, мало спал, была хорошая встреча...",
        height=120,
        key=f"note_{selected_date_str}"
    )

    button_text = "Обновить запись" if existing_entry is not None else "Сохранить запись"

    if st.button(button_text, type="primary", use_container_width=True):
        mood = MOOD_OPTIONS[selected_mood_label]
        save_entry(selected_date_str, mood, note)
        st.success("Запись сохранена.")
        st.rerun()

    if existing_entry is not None:
        st.divider()

        if st.button("Удалить запись за выбранную дату", use_container_width=True):
            delete_entry(selected_date_str)
            st.warning("Запись удалена.")
            st.rerun()


def show_stats_page():
    df = read_entries()

    if len(df) == 0:
        st.info("Пока нет записей. Сначала добавь настроение во вкладке Запись.")
        return

    total = len(df)

    positive = int((df["mood"] == "+").sum())
    neutral = int((df["mood"] == "0").sum())
    negative = int((df["mood"] == "-").sum())

    average = df["score"].mean()

    df_dates = df.copy()
    df_dates["date_dt"] = pd.to_datetime(df_dates["date"], errors="coerce")

    last_7_days = df_dates[
        df_dates["date_dt"] >= pd.Timestamp(today_date - timedelta(days=6))
    ]

    if len(last_7_days) > 0:
        average_7_days = last_7_days["score"].mean()
    else:
        average_7_days = 0

    col1, col2, col3 = st.columns(3)

    col1.metric("Всего записей", total)
    col2.metric("Среднее", round(average, 2))
    col3.metric("Среднее за 7 дней", round(average_7_days, 2))

    col4, col5, col6 = st.columns(3)

    col4.metric("Хороших дней", positive)
    col5.metric("Обычных дней", neutral)
    col6.metric("Плохих дней", negative)

    st.divider()

    st.subheader("Распределение настроений")

    chart_data = pd.DataFrame(
        {"Количество": [positive, neutral, negative]},
        index=["🙂 Хорошие", "😐 Обычные", "🙁 Плохие"]
    )

    st.bar_chart(chart_data)

    st.divider()

    st.subheader("Динамика настроения")

    line_data = df.copy()
    line_data["date"] = pd.to_datetime(line_data["date"], errors="coerce")
    line_data = line_data.dropna(subset=["date"])
    line_data = line_data.sort_values("date")
    line_data = line_data.set_index("date")

    st.line_chart(line_data["score"])

    st.caption("1 = хороший день, 0 = обычный день, -1 = плохой день.")


def show_history_page():
    df = read_entries()

    if len(df) == 0:
        st.info("Пока нет записей.")
        return

    period = st.selectbox(
        "Показать:",
        ["Все записи", "Последние 7 дней", "Последние 30 дней"]
    )

    history_df = df.copy()
    history_df["date_dt"] = pd.to_datetime(history_df["date"], errors="coerce")

    if period == "Последние 7 дней":
        history_df = history_df[
            history_df["date_dt"] >= pd.Timestamp(today_date - timedelta(days=6))
        ]

    elif period == "Последние 30 дней":
        history_df = history_df[
            history_df["date_dt"] >= pd.Timestamp(today_date - timedelta(days=29))
        ]

    history_df = history_df.sort_values("date_dt", ascending=False)

    history_df["Настроение"] = history_df["mood"].map(MOOD_NAMES)

    history_df = history_df.rename(columns={
        "date": "Дата",
        "score": "Оценка",
        "note": "Заметка"
    })

    history_df = history_df[["Дата", "Настроение", "Оценка", "Заметка"]]

    st.dataframe(history_df, use_container_width=True, hide_index=True)

    csv_data = df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Скачать данные CSV",
        data=csv_data,
        file_name="mood_log.csv",
        mime="text/csv",
        use_container_width=True
    )


if not check_password():
    st.stop()


st.title("Трекер настроения")
st.write("Записывай настроение, добавляй заметку и отслеживай динамику по дням.")

tab1, tab2, tab3 = st.tabs(["Запись", "Статистика", "История"])

with tab1:
    show_entry_page()

with tab2:
    show_stats_page()

with tab3:
    show_history_page()