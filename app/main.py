from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import List

import streamlit as st
from dotenv import load_dotenv

# Ensure project root is on sys.path so that 'app' package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.export import export_docx, export_pdf
from app.llm import bootstrap_spec, generate_title, next_questions, refine_spec
from app.spec_builder import append_assistant_message, append_user_answer
from app.state import AppState, Idea
from app.storage import delete_idea, get_idea, load_ideas, save_ideas

APP_TITLE = "Patent Chat"
DEFAULT_CATEGORY = "防災"
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "sample.md"


def init_session_state() -> None:
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()
    if "ideas" not in st.session_state:
        st.session_state.ideas = load_ideas()


def sidebar_ui():
    st.sidebar.title("アイデア一覧")
    ideas: List[Idea] = st.session_state.ideas
    state: AppState = st.session_state.app_state

    # New idea button
    if st.sidebar.button("＋ 新規アイデアを作成", use_container_width=True):
        state.show_new_idea_form = True

    # Idea list
    for idea in ideas:
        cols = st.sidebar.columns([0.7, 0.15, 0.15])
        if cols[0].button(f"{idea.title or '(無題)'}", key=f"sel-{idea.id}"):
            state.selected_idea_id = idea.id
            state.show_new_idea_form = False
        if cols[1].button("編集", key=f"edit-{idea.id}"):
            state.selected_idea_id = idea.id
            state.show_new_idea_form = True
        if cols[2].button("削除", key=f"del-{idea.id}"):
            st.session_state.ideas = delete_idea(ideas, idea.id)
            save_ideas(st.session_state.ideas)
            if state.selected_idea_id == idea.id:
                state.selected_idea_id = None


def new_idea_form():
    st.subheader("新規アイデア")
    category = st.selectbox(
        "カテゴリ", ["防災", "医療", "製造", "ソフトウェア", "環境", "その他"], index=0
    )
    description = st.text_area(
        "アイデアの詳細説明", height=160, placeholder="アイデアの概要を記載…"
    )
    cols = st.columns(2)
    if cols[0].button("保存"):
        idea_id = str(uuid.uuid4())
        title = generate_title(description)
        idea = Idea(id=idea_id, title=title, category=category, description=description)
        st.session_state.ideas.append(idea)
        save_ideas(st.session_state.ideas)
        st.session_state.app_state.selected_idea_id = idea_id
        st.session_state.app_state.show_new_idea_form = False
        st.success("保存しました。")
    if cols[1].button("キャンセル"):
        st.session_state.app_state.show_new_idea_form = False


def edit_idea_form(idea: Idea):
    st.subheader("アイデア編集")
    title = st.text_input("タイトル", value=idea.title)
    categories = ["防災", "医療", "製造", "ソフトウェア", "環境", "その他"]
    try:
        idx = categories.index(idea.category)
    except ValueError:
        idx = 0
    category = st.selectbox("カテゴリ", categories, index=idx)
    description = st.text_area("アイデアの詳細説明", value=idea.description, height=160)
    if st.button("更新"):
        idea.title = title
        idea.category = category
        idea.description = description
        save_ideas(st.session_state.ideas)
        st.success("更新しました。")


def hearing_ui(idea: Idea):
    st.subheader("AI ヒアリング")
    manual_md = SAMPLE_PATH.read_text(encoding="utf-8")

    # Bootstrap draft
    if not idea.draft_spec_markdown:
        with st.spinner("初期ドラフト生成中…"):
            idea.draft_spec_markdown = bootstrap_spec(manual_md, idea.description)
            save_ideas(st.session_state.ideas)

    # Conversation history
    for msg in idea.messages:
        role = "ユーザー" if msg["role"] == "user" else "AI"
        st.markdown(f"**{role}:** {msg['content']}")

    # Ask next questions
    if st.button("次の質問を提示"):
        with st.spinner("質問を準備中…"):
            qs = next_questions(manual_md, idea.messages, num_questions=3)
            for q in qs:
                append_assistant_message(idea.messages, q)
            save_ideas(st.session_state.ideas)

    # Quick answer buttons (Yes/No)
    cols = st.columns(3)
    if cols[0].button("はい"):
        append_user_answer(idea.messages, "はい")
        save_ideas(st.session_state.ideas)
    if cols[1].button("いいえ"):
        append_user_answer(idea.messages, "いいえ")
        save_ideas(st.session_state.ideas)
    with cols[2]:
        free_text = st.text_input("自由入力")
        if st.button("送信") and free_text:
            append_user_answer(idea.messages, free_text)
            save_ideas(st.session_state.ideas)

    # Improve draft from transcript
    if st.button("ドラフトを更新"):
        with st.spinner("ドラフト更新中…"):
            idea.draft_spec_markdown = refine_spec(
                manual_md, idea.messages, idea.draft_spec_markdown
            )
            save_ideas(st.session_state.ideas)

    st.divider()
    st.subheader("ドラフト")
    st.markdown(idea.draft_spec_markdown or "未生成", unsafe_allow_html=False)

    with st.expander("ドラフトを編集"):
        edited = st.text_area("Markdown", value=idea.draft_spec_markdown, height=360)
        if st.button("編集内容を保存"):
            idea.draft_spec_markdown = edited
            save_ideas(st.session_state.ideas)
            st.success("保存しました。")

    # Export (always available as download buttons)
    c1, c2 = st.columns(2)
    name_docx, data_docx = export_docx(idea.title, idea.draft_spec_markdown)
    c1.download_button(
        "Word を保存",
        data=data_docx,
        file_name=name_docx,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
    )
    name_pdf, data_pdf = export_pdf(idea.title, idea.draft_spec_markdown)
    c2.download_button(
        "PDF を保存",
        data=data_pdf,
        file_name=name_pdf,
        mime="application/pdf",
        use_container_width=True,
    )


def main():
    load_dotenv()
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("特許出願アイデアを対話で具体化し、明細書草案を生成します。")

    # Dark theme note: instruct Streamlit to use base dark theme via config.toml if desired

    init_session_state()
    sidebar_ui()

    ideas: List[Idea] = st.session_state.ideas
    state: AppState = st.session_state.app_state

    # Main area
    if state.show_new_idea_form and state.selected_idea_id:
        # edit selected
        idea = get_idea(ideas, state.selected_idea_id)
        if idea:
            edit_idea_form(idea)
    elif state.show_new_idea_form:
        new_idea_form()
    else:
        # default: list or selected idea view
        if state.selected_idea_id:
            idea = get_idea(ideas, state.selected_idea_id)
            if idea:
                st.header(idea.title)
                st.markdown(f"**カテゴリ:** {idea.category}")
                st.markdown(f"**概要:** {idea.description}")
                if st.button("対話開始 / 続きから"):
                    st.session_state.start_hearing = True
                if st.session_state.get("start_hearing"):
                    hearing_ui(idea)
            else:
                st.info("アイデアを選択してください。")
        else:
            st.info("左のサイドバーからアイデアを選択するか、新規作成してください。")


if __name__ == "__main__":
    main()
