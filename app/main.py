from __future__ import annotations

import logging
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any, List, Tuple, cast

import streamlit as st
from dotenv import load_dotenv

# Ensure project root is on sys.path so that 'app' package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth import render_login_gate, render_sidebar_user
from app.export import export_docx, export_pdf
from app.file_handler import process_uploaded_file_with_gemini
from app.llm import (
    DEFAULT_MODEL_NAME,
    bootstrap_spec,
    check_spec_completeness,
    generate_title,
    next_questions,
    regenerate_spec,
)
from app.spec_builder import append_assistant_message, append_user_answer
from app.state import AppState, Attachment, Idea
from app.storage import delete_idea, get_idea, load_ideas, save_ideas

APP_TITLE = "Patent Chat"
DEFAULT_CATEGORY = "防災"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Suppress very noisy PDF parsing warnings (e.g., advanced encodings)
logging.getLogger("pypdf").setLevel(logging.ERROR)


def _load_instruction_markdown() -> str:
    """Load drafting instruction document with fallback to sample.md."""
    primary = PROJECT_ROOT / "LLM_Prompt_for_Patent_Application_Drafting_from_Idea.md"
    fallback = PROJECT_ROOT / "sample.md"
    path = primary if primary.exists() else fallback
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _clean_ai_message(content: str) -> str:
    """AIメッセージから導入部分を除外して本文のみ返す."""
    if not content:
        return ""

    # 除外パターン（一般的な導入表現）
    intro_patterns = [
        r'^承知.*?。\s*',
        r'^了解.*?。\s*',
        r'^確認させて.*?。\s*',
        r'^わかりました.*?。\s*',
        r'^ありがとうございます.*?。\s*',
        r'^それでは.*?。\s*',
        r'^以下.*?確認.*?。\s*',
        r'^次の点について.*?。\s*',
        r'^追加で確認.*?。\s*',
    ]

    cleaned = content.strip()

    # 各パターンで導入部分を除去
    for pattern in intro_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.DOTALL)

    # 冒頭の空行を除去
    cleaned = re.sub(r'^\s*\n+', '', cleaned)

    return cleaned.strip()


def init_session_state() -> None:
    if "app_state" not in st.session_state:
        default_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)
        st.session_state.app_state = AppState(gemini_model=default_model)
        os.environ["GEMINI_MODEL"] = default_model
    if "ideas" not in st.session_state:
        st.session_state.ideas = load_ideas()


def sidebar_ui():
    ideas: List[Idea] = st.session_state.ideas
    state: AppState = st.session_state.app_state

    # Always-available Home navigation (without logging out)
    if st.sidebar.button("🏠 トップへ戻る", use_container_width=True):
        state.selected_idea_id = None
        state.show_new_idea_form = False
        # Clear transient flags such as hearing start
        if "start_hearing" in st.session_state:
            st.session_state.pop("start_hearing", None)
        st.rerun()

    model_options = ["gemini-2.5-pro", "gemini-2.5-flash"]
    current_index = (
        model_options.index(state.gemini_model) if state.gemini_model in model_options else 0
    )
    selected_model = st.sidebar.selectbox("Geminiモデル", model_options, index=current_index)
    if selected_model != state.gemini_model:
        state.gemini_model = selected_model
        os.environ["GEMINI_MODEL"] = selected_model

    # Move the idea list title below the model selector
    st.sidebar.title("アイデア一覧")

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

    # File upload section
    st.markdown("### 関連ファイルの添付（任意）")
    uploaded_files = st.file_uploader(
        "ファイルを選択",
        accept_multiple_files=True,
        help="テキスト、PDF、画像、Word、PowerPointファイルをアップロードできます（各10MB以内）",
    )

    # Process uploaded files
    attachments_to_add = []
    if uploaded_files:
        for uploaded_file in uploaded_files:
            comment = st.text_input(
                f"{uploaded_file.name} へのコメント",
                placeholder="このファイルの説明を入力...",
                key=f"comment_{uploaded_file.name}",
            )
            attachments_to_add.append((uploaded_file, comment))

    cols = st.columns(2)
    if cols[0].button("保存", type="primary"):
        idea_id = str(uuid.uuid4())
        with st.status("処理を開始します…", expanded=True) as status:
            status.update(label="タイトル生成中…", state="running")
            title = generate_title(description)

            # Process attachments
            status.update(label="添付ファイルを処理中…", state="running")
            attachments = []
            attachment_dicts = []
            gemini_files: List[Any] = []

            # Get Gemini client to fetch file objects
            import logging
            import os

            from google import genai

            logger = logging.getLogger("patent_chat.main")
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            gemini_client = None
            if api_key:
                try:
                    gemini_client = genai.Client(api_key=api_key)
                except Exception:
                    pass

            for uploaded_file, comment in attachments_to_add:
                try:
                    file_data = process_uploaded_file_with_gemini(uploaded_file, comment)
                    attachment = Attachment(
                        filename=file_data["filename"],
                        content_base64=file_data["content_base64"],
                        comment=file_data["comment"],
                        file_type=file_data["file_type"],
                        upload_time=file_data["upload_time"],
                        gemini_file_id=file_data.get("gemini_file_id"),
                        gemini_mime_type=file_data.get("gemini_mime_type"),
                        extracted_text=file_data.get("extracted_text"),
                    )
                    attachments.append(attachment)
                    attachment_dicts.append(
                        {
                            "filename": file_data["filename"],
                            "extracted_text": file_data["extracted_text"],
                            "comment": file_data["comment"],
                        }
                    )

                    # Add Gemini file object if available
                    if file_data.get("gemini_file_id") and gemini_client:
                        try:
                            # Get the actual file object from Gemini
                            gemini_file = gemini_client.files.get(name=file_data["gemini_file_id"])
                            gemini_files.append(gemini_file)
                        except Exception:
                            file_id = file_data['gemini_file_id']
                            logger.warning(f"Failed to get Gemini file object for {file_id}")
                    elif file_data.get("gemini_file_id"):
                        # No client available, just store the ID
                        gemini_files.append(file_data["gemini_file_id"])

                except Exception as e:
                    st.warning(f"ファイル {uploaded_file.name} の処理に失敗しました: {str(e)}")

            status.update(label="アイデアを保存中…", state="running")
            idea = Idea(
                id=idea_id,
                title=title,
                category=category,
                description=description,
                attachments=attachments,
            )
            st.session_state.ideas.append(idea)
            save_ideas(st.session_state.ideas)

            status.update(label="初期ドラフト生成中…", state="running")
            manual_md = _load_instruction_markdown()
            spec_result, error_msg = bootstrap_spec(
                manual_md, idea.description, attachments=attachment_dicts, gemini_files=gemini_files
            )
            if error_msg:
                st.error(f"⚠️ {error_msg}")
                st.info("基本的な骨格を生成しました。後で再生成を試してください。")
            idea.draft_spec_markdown = spec_result
            save_ideas(st.session_state.ideas)

            status.update(label="初回質問を準備中…", state="running")
            qs, q_error = next_questions(
                manual_md,
                idea.messages,
                idea.draft_spec_markdown,
                num_questions=5,
                version=idea.draft_version,
                is_final=idea.is_final,
                attachments=attachment_dicts,
            )
            if q_error:
                st.warning(f"⚠️ 質問生成エラー: {q_error}")
                st.info("デフォルトの質問を使用します。")
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


def _calculate_question_start_number(idea: Idea) -> int:
    """Calculate the starting number for questions based on all previous questions."""
    # Count all assistant messages that are questions (answered or not)
    question_count = 0
    for msg in idea.messages:
        if msg.get("role") == "assistant":
            # Simple heuristic: if it contains "？" or "?", it's likely a question
            content = msg.get("content", "")
            if "？" in content or "?" in content:
                question_count += 1

    # If we're on the first version or no questions yet, start from 1
    if question_count == 0:
        return 1

    # Count only answered questions (pairs of assistant followed by user)
    answered_count = 0
    i = 0
    while i < len(idea.messages):
        # Look for assistant messages
        if i < len(idea.messages) and idea.messages[i].get("role") == "assistant":
            # Check if there's at least one user answer after this batch of questions
            j = i
            # Skip all consecutive assistant messages
            while j < len(idea.messages) and idea.messages[j].get("role") == "assistant":
                j += 1
            # Now j points to first non-assistant message or end
            # Check if there are user messages
            if j < len(idea.messages) and idea.messages[j].get("role") == "user":
                # Count the assistant messages in this batch as answered
                for k in range(i, j):
                    content = idea.messages[k].get("content", "")
                    if "？" in content or "?" in content:
                        answered_count += 1
            i = j
        else:
            i += 1

    # Start numbering from answered_count + 1
    return answered_count + 1


def _prepare_attachment_dicts(idea: Idea) -> Tuple[List[dict], List]:
    """Convert Attachment objects to dictionaries for LLM functions.

    Returns:
        Tuple of (attachment_dicts, gemini_files)
    """
    import base64

    from app.file_handler import extract_text_from_file

    attachment_dicts = []
    gemini_files: List[Any] = []

    # Get Gemini client to fetch file objects
    import logging
    import os

    from google import genai

    logger = logging.getLogger("patent_chat.main")
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    gemini_client = None
    if api_key:
        try:
            gemini_client = genai.Client(api_key=api_key)
        except Exception:
            pass

    for att in idea.attachments:
        # Check if we have a Gemini file ID
        if att.gemini_file_id and gemini_client:
            try:
                # Get the actual file object from Gemini
                gemini_file = gemini_client.files.get(name=att.gemini_file_id)
                gemini_files.append(gemini_file)
            except Exception:
                logger.warning(f"Failed to get Gemini file object for {att.gemini_file_id}")
        elif att.gemini_file_id:
            # No client available, just store the ID
            gemini_files.append(cast(Any, att.gemini_file_id))
            # Still add to dicts for backward compatibility
            attachment_dicts.append(
                {
                    "filename": att.filename,
                    "extracted_text": "",  # Will be processed by Gemini directly
                    "comment": att.comment,
                }
            )
        else:
            # No Gemini file ID: use stored extracted_text if available to avoid re-parsing
            if getattr(att, "extracted_text", None):
                attachment_dicts.append(
                    {
                        "filename": att.filename,
                        "extracted_text": att.extracted_text or "",
                        "comment": att.comment,
                    }
                )
            else:
                # Fall back to local extraction
                file_bytes = base64.b64decode(att.content_base64)
                extracted_text = extract_text_from_file(file_bytes, att.filename)
                attachment_dicts.append(
                    {
                        "filename": att.filename,
                        "extracted_text": extracted_text,
                        "comment": att.comment,
                    }
                )

    return attachment_dicts, gemini_files


def _render_hearing_section(idea: Idea, manual_md: str, show_questions_first: bool = False):
    """共通の質問表示ロジック."""
    # Hearing round equals draft version
    hearing_round = idea.draft_version

    st.subheader(f"AI ヒアリング（第{hearing_round}回）")

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

    # For version 2+, show questions first if requested
    if show_questions_first and pending_questions:
        _render_pending_questions(idea, pending_questions, manual_md)

    # Conversation history (exclude pending questions to avoid duplication)
    if any(i not in to_hide_indices for i in range(len(idea.messages))):
        # Properly pair questions and answers considering batch format
        # Filter out pending questions first
        filtered_messages = []
        for i, msg in enumerate(idea.messages):
            if i not in to_hide_indices:
                filtered_messages.append(msg)

        # Collect questions and answers in batches
        questions = []
        answers = []

        j = 0
        while j < len(filtered_messages):
            # Collect consecutive assistant messages
            batch_questions = []
            while j < len(filtered_messages) and filtered_messages[j]["role"] == "assistant":
                batch_questions.append(_clean_ai_message(filtered_messages[j]['content']))
                j += 1

            # Collect consecutive user messages
            batch_answers = []
            while j < len(filtered_messages) and filtered_messages[j]["role"] == "user":
                batch_answers.append(filtered_messages[j]['content'])
                j += 1

            # Pair this batch
            for k in range(len(batch_questions)):
                if k < len(batch_answers):
                    questions.append(batch_questions[k])
                    answers.append(batch_answers[k])

        # Display Q&A history in expander for version 2+
        if show_questions_first and questions:
            with st.expander("**これまでの質問と回答**", expanded=False):
                # Display paired Q&A
                for q, a in zip(questions, answers):
                    st.markdown(f"{q}: {a}")
        elif not show_questions_first and questions:
            # Version 1: display inline
            for q, a in zip(questions, answers):
                st.markdown(f"{q}: {a}")

    # Pending assistant questions at tail -> per-question radios (はい/いいえ/わからない)
    if not show_questions_first and pending_questions:
        _render_pending_questions(idea, pending_questions, manual_md)


def _render_pending_questions(idea: Idea, pending_questions: list[str], manual_md: str):
    """Render pending questions form."""
    st.markdown("**未回答の質問**（各項目に回答して「回答をまとめて送信」）")
    with st.form(f"qa-form-{idea.id}"):
        selections: list[str] = []
        # Calculate the starting question number based on all previous questions
        start_num = _calculate_question_start_number(idea)
        for i, q in enumerate(pending_questions, start=start_num):
            cleaned_q = _clean_ai_message(q)
            st.markdown(f"Q{i}: {cleaned_q}")
            # Use draft version in key to ensure fresh state for each round
            choice = st.radio(
                key=f"ans-{idea.id}-v{idea.draft_version}-{i}",
                label="回答",
                options=["はい", "いいえ", "わからない"],
                index=2,  # Default to "わからない"
                horizontal=True,
            )
            selections.append(choice)
        submitted = st.form_submit_button("回答をまとめて送信", type="primary")
        if submitted:
            for ans in selections:
                append_user_answer(idea.messages, ans)
            with st.spinner("ドラフト更新中…"):
                attachment_dicts, gemini_files = _prepare_attachment_dicts(idea)
                spec_result, error_msg = regenerate_spec(
                    manual_md,
                    idea.description,
                    idea.messages,
                    attachments=attachment_dicts,
                    gemini_files=gemini_files,
                )
                if error_msg:
                    st.error(f"⚠️ {error_msg}")
                    st.info("前のバージョンを保持します。")
                else:
                    idea.draft_spec_markdown = spec_result
                    idea.draft_version += 1

                # Check if this should be the final version based on completeness only
                is_complete, score = check_spec_completeness(
                    manual_md, idea.draft_spec_markdown, idea.draft_version
                )
                print(
                    f"DEBUG: Completeness check - is_complete={is_complete}, "
                    f"score={score}, version={idea.draft_version}"
                )
                if is_complete:
                    idea.is_final = True
                    print(f"DEBUG: Set is_final=True due to completeness score={score}")

                save_ideas(st.session_state.ideas)

            # Generate next questions only if not final
            if not idea.is_final and not error_msg:  # Don't generate questions if error
                with st.spinner("次の質問を準備中…"):
                    try:
                        attachment_dicts, gemini_files = _prepare_attachment_dicts(idea)
                        qs2, q_error = next_questions(
                            manual_md,
                            idea.messages,
                            idea.draft_spec_markdown,
                            num_questions=5,
                            version=idea.draft_version,
                            is_final=idea.is_final,
                            attachments=attachment_dicts,
                        )
                        if q_error:
                            st.warning(f"⚠️ 質問生成エラー: {q_error}")
                            st.info("デフォルトの質問を使用します。")
                    except Exception as e:
                        print(f"ERROR: Exception in next_questions: {e}")
                        st.warning(f"⚠️ 質問生成で予期しないエラーが発生しました: {str(e)[:100]}")
                        st.info("デフォルトの質問を使用します。")
                        # Provide fallback questions
                        qs2 = [
                            "現行ドラフトに未記載箇所があります。図面は必要ですか？（はい/いいえ）",
                            "実施例は複数のバリエーションがありますか？（はい/いいえ）",
                            "発明の効果に定量的根拠はありますか？（はい/いいえ）",
                            "既存技術との違いを明確に説明できますか？（はい/いいえ）",
                            "この発明の最も重要な利点は何ですか？（はい/いいえで答えられる形で確認）",
                        ][:5]
                        q_error = "予期しないエラー"

                    print(f"DEBUG: Generated {len(qs2)} questions for version {idea.draft_version}")
                    # Always add questions even if there was an error
                    for q in qs2:
                        append_assistant_message(idea.messages, q)
                        print(f"DEBUG: Added question: {q[:50]}...")
                    save_ideas(st.session_state.ideas)
            else:
                print(
                    f"DEBUG: Skipping question generation - "
                    f"is_final={idea.is_final}, version={idea.draft_version}"
                )
            st.rerun()


def hearing_ui(idea: Idea):
    manual_md = _load_instruction_markdown()

    # File upload section for hearing
    with st.expander("追加ファイルをアップロード", expanded=False):
        st.markdown("ヒアリング中に追加で参考資料をアップロードできます")
        new_files = st.file_uploader(
            "ファイルを選択",
            accept_multiple_files=True,
            help="テキスト、PDF、画像、Word、PowerPointファイルをアップロードできます（各10MB以内）",
            key=f"hearing_upload_{idea.id}",
        )

        if new_files:
            attachments_to_add = []
            for uploaded_file in new_files:
                comment = st.text_input(
                    f"{uploaded_file.name} へのコメント",
                    placeholder="このファイルの説明を入力...",
                    key=f"hearing_comment_{idea.id}_{uploaded_file.name}",
                )
                attachments_to_add.append((uploaded_file, comment))

            if st.button("ファイルを追加", key=f"add_files_{idea.id}"):
                for uploaded_file, comment in attachments_to_add:
                    try:
                        file_data = process_uploaded_file_with_gemini(uploaded_file, comment)
                        attachment = Attachment(
                            filename=file_data["filename"],
                            content_base64=file_data["content_base64"],
                            comment=file_data["comment"],
                            file_type=file_data["file_type"],
                            upload_time=file_data["upload_time"],
                            gemini_file_id=file_data.get("gemini_file_id"),
                            gemini_mime_type=file_data.get("gemini_mime_type"),
                            extracted_text=file_data.get("extracted_text"),
                        )
                        idea.attachments.append(attachment)
                        st.success(f"{uploaded_file.name} を追加しました")
                    except Exception as e:
                        st.error(f"ファイル {uploaded_file.name} の処理に失敗しました: {str(e)}")
                save_ideas(st.session_state.ideas)
                st.rerun()

    # Display existing attachments
    if idea.attachments:
        with st.expander(f"添付ファイル ({len(idea.attachments)}件)", expanded=False):
            for att in idea.attachments:
                cols = st.columns([3, 1])
                cols[0].markdown(f"📎 **{att.filename}** - {att.comment}")
                import base64

                file_bytes = base64.b64decode(att.content_base64)
                cols[1].download_button(
                    "ダウンロード",
                    data=file_bytes,
                    file_name=att.filename,
                    mime=att.file_type,
                    key=f"download_{idea.id}_{att.filename}",
                )

    # Ensure draft exists
    if not idea.draft_spec_markdown:
        with st.spinner("初期ドラフト生成中…"):
            attachment_dicts, gemini_files = _prepare_attachment_dicts(idea)
            spec_result, error_msg = bootstrap_spec(
                manual_md, idea.description, attachments=attachment_dicts, gemini_files=gemini_files
            )
            if error_msg:
                st.error(f"⚠️ {error_msg}")
                st.info("基本的な骨格を生成しました。")
            idea.draft_spec_markdown = spec_result
            save_ideas(st.session_state.ideas)

    # Auto-generate initial questions if none exist yet (up to 5)
    if not any(m.get("role") == "assistant" for m in idea.messages) and not idea.is_final:
        with st.spinner("初回質問を準備中…"):
            attachment_dicts, gemini_files = _prepare_attachment_dicts(idea)
            qs, q_error = next_questions(
                manual_md,
                idea.messages,
                idea.draft_spec_markdown,
                num_questions=5,
                version=idea.draft_version,
                is_final=idea.is_final,
                attachments=attachment_dicts,
            )
            if q_error:
                st.warning(f"⚠️ 質問生成エラー: {q_error}")
                st.info("デフォルトの質問を使用します。")
            for q in qs:
                append_assistant_message(idea.messages, q)
            save_ideas(st.session_state.ideas)
        st.rerun()

    # Handle final version display
    if idea.is_final:
        version_label = f"第{idea.draft_version}版（最終版）"
        st.subheader(f"特許明細書 - {version_label}")
        st.info("✅ 明細書が完成しました。以下から編集・ダウンロードが可能です。")

        # Show full draft expanded for final version
        st.markdown(idea.draft_spec_markdown or "未生成", unsafe_allow_html=False)

        # Edit and export options
        with st.expander("明細書を編集"):
            edited = st.text_area("Markdown", value=idea.draft_spec_markdown, height=500)
            if st.button("編集内容を保存"):
                idea.draft_spec_markdown = edited
                save_ideas(st.session_state.ideas)
                st.success("保存しました。")

        # Export buttons
        st.markdown("### エクスポート")
        c1, c2 = st.columns(2)
        name_docx, data_docx = export_docx(idea.title, idea.draft_spec_markdown)
        c1.download_button(
            "📝 Word でダウンロード",
            data=data_docx,
            file_name=name_docx,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            type="primary",
        )
        name_pdf, data_pdf = export_pdf(idea.title, idea.draft_spec_markdown)
        c2.download_button(
            "📄 PDF でダウンロード",
            data=data_pdf,
            file_name=name_pdf,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

        # Show Q&A history at the bottom
        with st.expander("質疑応答履歴", expanded=False):
            # Properly pair questions and answers considering batch format
            questions = []
            answers = []

            j = 0
            while j < len(idea.messages):
                # Collect consecutive assistant messages
                batch_questions = []
                while j < len(idea.messages) and idea.messages[j]["role"] == "assistant":
                    batch_questions.append(_clean_ai_message(idea.messages[j]['content']))
                    j += 1

                # Collect consecutive user messages
                batch_answers = []
                while j < len(idea.messages) and idea.messages[j]["role"] == "user":
                    batch_answers.append(idea.messages[j]['content'])
                    j += 1

                # Pair this batch
                for k in range(len(batch_questions)):
                    if k < len(batch_answers):
                        questions.append(batch_questions[k])
                        answers.append(batch_answers[k])
                    else:
                        questions.append(batch_questions[k])
                        answers.append("(未回答)")

            # Display Q&A pairs (question: answer on same line)
            for q, a in zip(questions, answers):
                st.markdown(f"{q}: {a}")

    # Non-final version display
    elif idea.draft_version == 1:
        # Version 1: Questions first layout
        _render_hearing_section(idea, manual_md, show_questions_first=False)

        # Draft in collapsed expander
        with st.expander("生成された明細書ドラフト（第1版）", expanded=False):
            st.markdown(idea.draft_spec_markdown or "未生成", unsafe_allow_html=False)

    else:
        # Version 2-4: New layout - questions first, then history, then draft
        st.subheader("AI ヒアリング")

        # Show questions first, then Q&A history
        _render_hearing_section(idea, manual_md, show_questions_first=True)

        st.divider()

        # Draft at bottom (collapsed)
        version_label = f"第{idea.draft_version}版"
        with st.expander(f"生成された明細書ドラフト（{version_label}）", expanded=False):
            st.markdown(idea.draft_spec_markdown or "未生成", unsafe_allow_html=False)

            # Limited export for non-final versions
            st.markdown("---")
            st.caption("※ ドラフトのエクスポート（現在の状態）")
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
    # Basic authentication gate (enabled via env: BASIC_AUTH_USERNAME/PASSWORD)
    render_login_gate(st)
    st.title(APP_TITLE)
    st.caption("特許出願アイデアを対話で具体化し、明細書草案を生成します。")

    # Dark theme note: instruct Streamlit to use base dark theme via config.toml if desired

    init_session_state()
    # Sidebar user info + logout when auth enabled
    render_sidebar_user(st)
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
