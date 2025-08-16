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
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_instruction_markdown() -> str:
    """Load drafting instruction document with fallback to sample.md."""
    primary = PROJECT_ROOT / "LLM_Prompt_for_Patent_Application_Drafting_from_Idea.md"
    fallback = PROJECT_ROOT / "sample.md"
    path = primary if primary.exists() else fallback
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


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
        st.rerun()

    # Idea list
    for idea in ideas:
        cols = st.sidebar.columns([0.7, 0.15, 0.15])
        if cols[0].button(f"{idea.title or '(無題)'}", key=f"sel-{idea.id}"):
            state.selected_idea_id = idea.id
            state.show_new_idea_form = False
            st.rerun()
        if cols[1].button("編集", key=f"edit-{idea.id}"):
            state.selected_idea_id = idea.id
            state.show_new_idea_form = True
            st.rerun()
        if cols[2].button("削除", key=f"del-{idea.id}"):
            st.session_state.ideas = delete_idea(ideas, idea.id)
            save_ideas(st.session_state.ideas)
            if state.selected_idea_id == idea.id:
                state.selected_idea_id = None
            st.rerun()


def new_idea_form():
    st.subheader("新規アイデア")
    category = st.selectbox(
        "カテゴリ", ["防災", "医療", "製造", "ソフトウェア", "環境", "その他"], index=0
    )
    description = st.text_area(
        "アイデアの詳細説明", height=160, placeholder="アイデアの概要を記載…"
    )
    cols = st.columns(2)
    if cols[0].button("保存", type="primary"):
        idea_id = str(uuid.uuid4())
        with st.status("処理を開始します…", expanded=True) as status:
            status.update(label="タイトル生成中…", state="running")
            title = generate_title(description)

            status.update(label="アイデアを保存中…", state="running")
            idea = Idea(
                id=idea_id,
                title=title,
                category=category,
                description=description,
            )
            st.session_state.ideas.append(idea)
            save_ideas(st.session_state.ideas)

            status.update(label="初期ドラフト生成中…", state="running")
            manual_md = _load_instruction_markdown()
            idea.draft_spec_markdown = bootstrap_spec(manual_md, idea.description)
            save_ideas(st.session_state.ideas)

            status.update(label="初回質問を準備中…", state="running")
            qs = next_questions(manual_md, idea.messages, idea.draft_spec_markdown, num_questions=5)
            for q in qs:
                append_assistant_message(idea.messages, q)
            save_ideas(st.session_state.ideas)

            status.update(label="完了", state="complete")

        st.session_state.app_state.selected_idea_id = idea_id
        st.session_state.app_state.show_new_idea_form = False
        st.session_state.start_hearing = True
        st.rerun()
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
    manual_md = _load_instruction_markdown()

    # Ensure draft exists
    if not idea.draft_spec_markdown:
        with st.spinner("初期ドラフト生成中…"):
            idea.draft_spec_markdown = bootstrap_spec(manual_md, idea.description)
            save_ideas(st.session_state.ideas)

    # Auto-generate initial questions if none exist yet (up to 5)
    if not any(m.get("role") == "assistant" for m in idea.messages):
        with st.spinner("初回質問を準備中…"):
            qs = next_questions(manual_md, idea.messages, idea.draft_spec_markdown, num_questions=5)
            for q in qs:
                append_assistant_message(idea.messages, q)
            save_ideas(st.session_state.ideas)
        st.rerun()

    # 1) Draft first
    st.subheader(f"ドラフト（第{idea.draft_version}版）")
    st.markdown(idea.draft_spec_markdown or "未生成", unsafe_allow_html=False)

    with st.expander("ドラフトを編集"):
        edited = st.text_area("Markdown", value=idea.draft_spec_markdown, height=360)
        if st.button("編集内容を保存"):
            idea.draft_spec_markdown = edited
            save_ideas(st.session_state.ideas)
            st.success("保存しました。")

    # Export
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

    st.divider()
    # 2) Hearing below
    st.subheader("AI ヒアリング")

    # Collect consecutive assistant messages at the tail (unanswered)
    tail_assistant: list[str] = []
    for m in reversed(idea.messages):
        if m.get("role") == "assistant":
            tail_assistant.append(m.get("content", ""))
        else:
            break
    tail_assistant = list(reversed(tail_assistant))

    # Heuristic: keep only yes/no style questions for the radio form
    def _looks_like_yes_no_question(text: str) -> bool:
        if not text:
            return False
        t = str(text).strip()
        if "はい/いいえ" in t or "（はい/いいえ" in t:
            return True
        if t.endswith("？") or t.endswith("?"):
            return True
        return False

    pending_candidates = [q for q in tail_assistant if _looks_like_yes_no_question(q)]
    # De-duplicate while preserving order
    seen_q: set[str] = set()
    pending_questions: list[str] = []
    for q in pending_candidates:
        if q not in seen_q:
            seen_q.add(q)
            pending_questions.append(q)
    pending_questions = pending_questions[:5]

    # Determine which trailing assistant messages to hide from the history
    # (exactly those shown in the pending questions)
    to_hide_indices = set()
    match_from_end = list(reversed(pending_questions))
    ptr = 0
    for idx in range(len(idea.messages) - 1, -1, -1):
        if ptr >= len(match_from_end):
            break
        m = idea.messages[idx]
        if m.get("role") != "assistant":
            break
        if m.get("content", "") == match_from_end[ptr]:
            to_hide_indices.add(idx)
            ptr += 1

    # Conversation history (exclude pending questions to avoid duplication)
    for i, msg in enumerate(idea.messages):
        if i in to_hide_indices:
            continue
        role = "ユーザー" if msg["role"] == "user" else "AI"
        st.markdown(f"**{role}:** {msg['content']}")

    # Ask next questions (up to 5)
    if st.button("次の質問を提示（最大5件）"):
        with st.spinner("質問を準備中…"):
            qs = next_questions(manual_md, idea.messages, idea.draft_spec_markdown, num_questions=5)
            for q in qs:
                append_assistant_message(idea.messages, q)
            save_ideas(st.session_state.ideas)
            st.rerun()

    # Pending assistant questions at tail -> per-question radios (はい/いいえ/わからない)
    if pending_questions:
        st.markdown("**未回答の質問**（各項目に回答して「回答をまとめて送信」）")
        with st.form(f"qa-form-{idea.id}"):
            selections: list[str] = []
            for i, q in enumerate(pending_questions, start=1):
                st.markdown(f"Q{i}: {q}")
                choice = st.radio(
                    key=f"ans-{idea.id}-{i}",
                    label="回答",
                    options=["はい", "いいえ", "わからない"],
                    index=2,
                    horizontal=True,
                )
                selections.append(choice)
            submitted = st.form_submit_button("回答をまとめて送信", type="primary")
            if submitted:
                for ans in selections:
                    append_user_answer(idea.messages, ans)
                with st.spinner("ドラフト更新中…"):
                    idea.draft_spec_markdown = refine_spec(
                        manual_md, idea.messages, idea.draft_spec_markdown
                    )
                    idea.draft_version += 1
                    save_ideas(st.session_state.ideas)
                # 新版表示後に次の質問を自動提示
                with st.spinner("次の質問を準備中…"):
                    qs2 = next_questions(
                        manual_md,
                        idea.messages,
                        idea.draft_spec_markdown,
                        num_questions=5,
                    )
                    for q in qs2:
                        append_assistant_message(idea.messages, q)
                    save_ideas(st.session_state.ideas)
                st.rerun()


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
