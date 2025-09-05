from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from google import genai
except ModuleNotFoundError:  # pragma: no cover
    genai = None  # type: ignore

from app.file_handler import _format_attachments_for_prompt

DEFAULT_MODEL_NAME = "gemini-2.5-pro"

# Logger (to terminal)
logger = logging.getLogger("patent_chat.llm")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)


def _classify_api_error(e: Exception) -> str:
    """エラーを分類してユーザーフレンドリーなメッセージを返す"""
    error_str = str(e).lower()

    # Check for 500 internal errors first
    if "500" in error_str or "internal" in error_str or "servererror" in error_str:
        return (
            "Geminiサーバーで一時的な問題が発生しています。"
            "数秒後に再試行してください。問題が続く場合は時間をおいてお試しください"
        )
    elif "api_key" in error_str or "api key" in error_str or "unauthorized" in error_str:
        return (
            "APIキーの設定を確認してください。"
            ".envファイルにGOOGLE_API_KEYまたはGEMINI_API_KEYを設定してください"
        )
    elif "rate" in error_str and "limit" in error_str or "quota" in error_str:
        return "API利用制限に達しました。しばらく待ってから再試行してください"
    elif "network" in error_str or "connection" in error_str:
        return "ネットワーク接続を確認してください"
    elif "timeout" in error_str:
        return "応答がタイムアウトしました。再試行してください"
    elif "invalid" in error_str and "response" in error_str:
        return "APIから予期しない応答を受け取りました。再試行してください"
    else:
        # エラーメッセージの最初の100文字を表示
        error_msg = str(e)[:200] if str(e) else "不明なエラー"
        return f"予期しないエラーが発生しました: {error_msg}"


def _is_internal_server_error(e: Exception) -> bool:
    """500やINTERNAL系のサーバーエラーかをゆるく判定する。

    google.genai.errors.ServerError 500 INTERNAL を想定しつつ、
    文言ベースでも検出できるようにしておく。
    """
    try:
        # メッセージ文字列での判定（ライブラリに依存しない）
        s = (str(e) or "").lower()
        if "500" in s or "internal" in s or "servererror" in s:
            return True
        # 追加のヒント（ステータスコード属性があれば参照）
        code = getattr(e, "status_code", None)
        if code == 500:
            return True
    except Exception:
        pass
    return False


def _title_model_name() -> str:
    """タイトル生成に利用する Gemini モデル名を返す"""
    # タイトル生成は常に軽量な Flash モデルを使用し、環境変数による上書きは不可
    return "gemini-2.5-flash"


def _get_client() -> Optional[Any]:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if genai is None or not api_key:
        logger.warning("Gemini API key is not set (GOOGLE_API_KEY or GEMINI_API_KEY).")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        logger.exception("Failed to initialize Gemini client.")
        return None


def _clean_llm_spec_text(text: str) -> str:
    """LLM出力のスペック本文から前置き・挨拶文などを除去して返す。

    - 日本語でありがちな導入定型（承知しました/了解しました/それでは 等）を先頭から削る
    - 先頭の空行を削除
    - 見出し（# ...）が途中に現れる場合は、それ以前の前置きを丸ごと除去
    """
    if not text:
        return ""

    cleaned = str(text)
    # BOM等を除去
    cleaned = cleaned.lstrip("\ufeff").lstrip()

    intro_patterns = [
        r"^はい[、,。\s]*承知.*?。\s*",
        r"^承知.*?。\s*",
        r"^了解.*?。\s*",
        r"^わかりました.*?。\s*",
        r"^ありがとうございます.*?。\s*",
        r"^それでは.*?。\s*",
        r"^では.*?。\s*",
        r"^以下.*?(示します|記します|作成します).*?\s*",
        r"^次の点について.*?。\s*",
        r"^追加で確認.*?。\s*",
    ]

    # 複数の前置きが連続する可能性があるため、繰り返し適用
    while True:
        changed = False
        for pattern in intro_patterns:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.DOTALL)
            if new_cleaned != cleaned:
                cleaned = new_cleaned
                changed = True
        # 先頭の空行を除去
        new_cleaned = re.sub(r"^\s*\n+", "", cleaned)
        if new_cleaned != cleaned:
            cleaned = new_cleaned
            changed = True
        if not changed:
            break

    # 見出し行が途中にある場合は、そこから開始させる（前置きの取りこぼし対策）
    m = re.search(r"(?m)^[ \t]*#{1,6}\s", cleaned)
    if m and m.start() > 0:
        cleaned = cleaned[m.start() :]

    return cleaned.strip()


def generate_title(idea_description: str) -> str:
    client = _get_client()
    if client is None:
        logger.warning("generate_title: No client. Falling back to first-line title.")
        return (idea_description.strip().splitlines()[0] or "新規アイデア")[:30]
    prompt = (
        "以下のアイデア概要から、特許明細書草案用の簡潔な日本語タイトルを1つ生成してください。\n"
        "出力はタイトルのみ。\n\n"
        f"アイデア概要:\n{idea_description}"
    )
    try:
        model_name = _title_model_name()
        logger.info(
            "generate_title: calling model=%s, idea_len=%d",
            model_name,
            len(idea_description or ""),
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        _log_response_debug("generate_title", resp)
        text = (resp.text or "").strip()
        if not text:
            logger.warning("generate_title: Empty response; falling back to first-line title.")
            return (idea_description.strip().splitlines()[0] or "新規アイデア")[:30]
        return text[:120]
    except Exception:
        logger.exception("generate_title: Gemini API error; falling back to first-line title.")
        return (idea_description.strip().splitlines()[0] or "新規アイデア")[:30]


def bootstrap_spec(
    sample_manual_md: str,
    idea_description: str,
    attachments: Optional[List[Dict]] = None,
    gemini_files: Optional[List] = None,
) -> Tuple[str, Optional[str]]:
    client = _get_client()
    if client is None:
        error_msg = "APIクライアントの初期化に失敗しました。APIキーの設定を確認してください"
        logger.warning("bootstrap_spec: No client; generating fallback skeleton.")
        return _fallback_skeleton(sample_manual_md, idea_description), error_msg
    system = (
        "あなたは特許明細書の下書きを作る専門家です。与えられた指示書（プロンプト）を最優先で参照し、"
        "不足部分は'未記載'と明示しつつ、Markdownで初稿を作ってください。"
    )

    # Format attachments if provided
    attachments_section = ""
    if attachments:
        formatted_attachments = _format_attachments_for_prompt(attachments)
        if formatted_attachments:
            attachments_section = f"\n[添付ファイル情報]\n{formatted_attachments}\n"

    prompt = (
        f"[指示書]\n{sample_manual_md}\n\n"
        f"[アイデア概要]\n{idea_description}\n"
        f"{attachments_section}\n"
        "[出力要件]\n"
        "- 見出しは手順書の順序に従う\n"
        "- 箇条書き可\n"
        "- 未確定箇所は '未記載' と記す\n"
        "- 前置きや挨拶は不要（本文のみを出力）\n"
        "- 添付ファイルの情報を適切に反映させる\n"
        if attachments
        else f"[指示書]\n{sample_manual_md}\n\n"
        f"[アイデア概要]\n{idea_description}\n\n"
        "[出力要件]\n"
        "- 見出しは手順書の順序に従う\n"
        "- 箇条書き可\n"
        "- 未確定箇所は '未記載' と記す\n"
        "- 前置きや挨拶は不要（本文のみを出力）\n"
    )
    try:
        model_name = _model_name()
        logger.info(
            "bootstrap_spec: calling model=%s, instruction_len=%d, idea_len=%d, gemini_files=%d",
            model_name,
            len(sample_manual_md or ""),
            len(idea_description or ""),
            len(gemini_files or []),
        )

        # Build contents array with Gemini files if available
        if gemini_files:
            # Create contents array - files first, then text prompt
            # gemini_files should be file objects or file IDs
            contents: List[Any] = []

            # Add files first
            for file_info in gemini_files:
                if isinstance(file_info, str):
                    # It's a file ID/URI, add directly
                    contents.append(file_info)
                elif hasattr(file_info, 'name'):
                    # It's a file object, use it directly
                    contents.append(file_info)
                else:
                    # Unsupported format, skip
                    logger.warning(f"Unsupported file format: {type(file_info)}")

            # Add the text prompt after files
            contents.append(f"{system}\n\n{prompt}")

            resp = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
        else:
            resp = client.models.generate_content(
                model=model_name,
                contents=f"{system}\n\n{prompt}",
            )
        _log_response_debug("bootstrap_spec", resp)
        text = _clean_llm_spec_text((resp.text or "").strip())
        if not text:
            error_msg = "APIから空の応答を受け取りました。再試行してください"
            logger.error("bootstrap_spec: Empty response text; using fallback skeleton.")
            return _fallback_skeleton(sample_manual_md, idea_description), error_msg
        return text, None
    except Exception as e:
        error_msg = _classify_api_error(e)
        logger.exception("bootstrap_spec: Gemini API error; using fallback skeleton.")
        return _fallback_skeleton(sample_manual_md, idea_description), error_msg


def next_questions(
    instruction_md: str,
    transcript: List[Dict[str, str]],
    current_spec_md: str,
    num_questions: int = 3,
    version: int = 1,
    is_final: bool = False,
    attachments: Optional[List[Dict]] = None,
) -> Tuple[List[str], Optional[str]]:
    # Don't generate questions if already finalized
    if is_final:
        return [], None

    client = _get_client()
    if client is None:
        error_msg = "API接続に失敗したため、標準的な質問を使用します"
        return [
            "現行ドラフトに未記載箇所があります。図面は必要ですか？（はい/いいえ）",
            "実施例は複数のバリエーションがありますか？（はい/いいえ）",
            "発明の効果に定量的根拠はありますか？（はい/いいえ）",
            "競合技術との差異は明確ですか？（はい/いいえ）",
            "用語の定義は十分ですか？（はい/いいえ）",
            "各構成要件の関係は明確ですか？（はい/いいえ）",
            "課題解決手段は過不足なく記載されていますか？（はい/いいえ）",
            "図面の参照番号は一貫していますか？（はい/いいえ）",
            "この発明の想定される応用例は何ですか？（自由記述）",
            "特に強調したい技術的効果は何ですか？（自由記述）",
        ][:num_questions], error_msg

    transcript_str = "\n".join([f"{m['role']}: {m['content']}" for m in transcript][-20:])
    system = (
        "あなたは特許明細書の執筆アシスタントです。以下の指示書に照らして、"
        "現行ドラフトの不足・曖昧・未記載部分を見つけ、ユーザーが答えやすい"
        "質問を優先度順に作成してください。"
    )

    # Format attachments if provided
    attachments_section = ""
    if attachments:
        formatted_attachments = _format_attachments_for_prompt(attachments)
        if formatted_attachments:
            attachments_section = f"\n[添付ファイル]\n{formatted_attachments}\n"

    prompt = (
        f"[指示書]\n{instruction_md}\n\n"
        f"[現行ドラフト(Markdown)]\n{current_spec_md}\n\n"
        f"[これまでの対話]\n{transcript_str}\n"
        f"{attachments_section}\n"
        "[出力要件]\n"
        "- 質問のみを出力（前置きや挨拶は不要）\n"
        "- 各行1問、{num}問\n"
        "- 最初の8問は『はい/いいえ』で答えられる形式（例: '〜ですか？（はい/いいえ）'）\n"
        "- 最後の2問は自由記述形式（末尾に'（自由記述）'）で、"
        "『〜ありますか？』や『〜ですか？』などの二択誘導を避け、"
        "『どのような』『なぜ』『何』『具体例を挙げて』等の表現を用いる\n"
        "- 1つの質問につき1論点、具体的に\n"
        "- 既に回答済みの重複質問は避ける\n"
        "- 添付ファイルの内容も考慮する\n".replace("{num}", str(num_questions))
        if attachments
        else f"[指示書]\n{instruction_md}\n\n"
        f"[現行ドラフト(Markdown)]\n{current_spec_md}\n\n"
        f"[これまでの対話]\n{transcript_str}\n\n"
        "[出力要件]\n"
        "- 質問のみを出力（前置きや挨拶は不要）\n"
        "- 各行1問、{num}問\n"
        "- 最初の8問は『はい/いいえ』で答えられる形式（例: '〜ですか？（はい/いいえ）'）\n"
        "- 最後の2問は自由記述形式（末尾に'（自由記述）'）で、"
        "『〜ありますか？』や『〜ですか？』などの二択誘導を避け、"
        "『どのような』『なぜ』『何』『具体例を挙げて』等の表現を用いる\n"
        "- 1つの質問につき1論点、具体的に\n"
        "- 既に回答済みの重複質問は避ける\n".replace("{num}", str(num_questions))
    )
    try:
        model_name = _model_name()
        logger.info(
            (
                "next_questions: calling model=%s, instruction_len=%d, "
                "transcript_turns=%d, draft_len=%d, n=%d"
            ),
            model_name,
            len(instruction_md or ""),
            len(transcript or []),
            len(current_spec_md or ""),
            num_questions,
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=f"{system}\n\n{prompt}",
        )
        _log_response_debug("next_questions", resp)
        text = resp.text or ""
    except Exception as e:
        error_msg = _classify_api_error(e)
        logger.exception("next_questions: Gemini API error; using canned questions.")
        return [
            "課題の技術的背景は十分に記載されていますか？（はい/いいえ）",
            "構成要件の必須/任意が明確ですか？（はい/いいえ）",
            "変形例はありますか？（はい/いいえ）",
            "図面と説明との整合性は取れていますか？（はい/いいえ）",
            "請求項の範囲は適切ですか？（はい/いいえ）",
            "従来技術との差異は明確ですか？（はい/いいえ）",
            "発明の効果は再現可能ですか？（はい/いいえ）",
            "実施形態の各段階は網羅されていますか？（はい/いいえ）",
            "他に記載しておくべき関連技術は何ですか？（自由記述）",
            "今後の改良案や展望はどのようなものですか？（自由記述）",
        ][:num_questions], error_msg
    lines = [line.strip("- ") for line in text.splitlines() if line.strip()]

    # Enforce 8 yes/no + 2 open when requesting 10 questions
    # Open questions: mark with '（自由記述）' and ensure they don't include 'はい/いいえ'
    # Yes/No questions: ensure they include '（はい/いいえ）'
    def _normalize_yesno_marker(s: str) -> str:
        # Remove any existing open marker
        s = re.sub(r"（自由記述）$", "", s).strip()
        # If already contains yes/no hint, leave as-is; otherwise append
        if ("はい/いいえ" not in s) and ("（はい/いいえ" not in s):
            s = f"{s}（はい/いいえ）"
        return s

    def _normalize_open_marker(s: str) -> str:
        # Remove yes/no markers anywhere if bracketed
        s = re.sub(r"（はい/いいえ[^）]*）", "", s).strip()
        # Avoid duplicated open marker
        if not s.endswith("（自由記述）"):
            s = f"{s}（自由記述）"
        return s

    lines = [line for line in lines if line][:num_questions]

    # If fewer than requested, pad with canonical prompts
    if len(lines) < num_questions:
        pad_pool = [
            "図面の参照番号は一貫していますか？（はい/いいえ）",
            "実施例は複数のバリエーションがありますか？（はい/いいえ）",
            "競合技術との差異は明確ですか？（はい/いいえ）",
            "この発明の想定される応用例は何ですか？（自由記述）",
            "特に強調したい技術的効果はありますか？（自由記述）",
        ]
        for p in pad_pool:
            if len(lines) >= num_questions:
                break
            lines.append(p)

    if num_questions >= 10 and len(lines) >= num_questions:
        # First num_questions-2 as yes/no, last 2 as open
        cutoff = num_questions - 2
        adjusted: List[str] = []
        for idx, q in enumerate(lines[:num_questions]):
            if idx < cutoff:
                adjusted.append(_normalize_yesno_marker(q))
            else:
                adjusted.append(_normalize_open_marker(q))
        lines = adjusted

    return lines, None


def refine_spec(
    sample_manual_md: str, transcript: List[Dict[str, str]], current_spec_md: str
) -> str:
    client = _get_client()
    if client is None:
        logger.warning("refine_spec: No client; leaving spec unchanged.")
        return current_spec_md
    transcript_str = "\n".join([f"{m['role']}: {m['content']}" for m in transcript][-30:])
    prompt = (
        "対話で得られた情報を既存ドラフトに反映して改善してください。\n"
        f"手順書:\n{sample_manual_md}\n\n"
        f"対話:\n{transcript_str}\n\n"
        f"現行ドラフト(Markdown):\n{current_spec_md}\n\n"
        "出力は更新後のMarkdown全文のみ。前置きや挨拶は不要（本文のみを出力）。"
    )
    try:
        model_name = _model_name()
        logger.info(
            "refine_spec: calling model=%s, instruction_len=%d, transcript_turns=%d, draft_len=%d",
            model_name,
            len(sample_manual_md or ""),
            len(transcript or []),
            len(current_spec_md or ""),
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        _log_response_debug("refine_spec", resp)
        text = _clean_llm_spec_text((resp.text or "").strip())
        if not text:
            logger.warning("refine_spec: Empty response; leaving spec unchanged.")
            return current_spec_md
        return text
    except Exception:
        logger.exception("refine_spec: Gemini API error; leaving spec unchanged.")
        return current_spec_md


def regenerate_spec(
    instruction_md: str,
    idea_description: str,
    transcript: List[Dict[str, str]],
    attachments: Optional[List[Dict]] = None,
    gemini_files: Optional[List] = None,
) -> Tuple[str, Optional[str]]:
    """
    Regenerate the entire specification from scratch using all available information.

    Unlike refine_spec which patches the existing draft, this function creates
    a complete new specification incorporating:
    - The original idea description
    - All Q&A information collected so far
    - The instruction document guidelines

    Args:
        instruction_md: The instruction document for patent drafting
        idea_description: The original idea description
        transcript: List of Q&A messages (assistant questions and user answers)

    Returns:
        Complete regenerated specification in Markdown format
    """
    client = _get_client()
    if client is None:
        error_msg = "APIクライアントの初期化に失敗しました。APIキーの設定を確認してください"
        logger.warning("regenerate_spec: No client; generating fallback skeleton.")
        return _fallback_skeleton(instruction_md, idea_description), error_msg

    # Format Q&A history for better understanding
    # Simple approach: collect all questions and answers in order
    questions = []
    answers = []

    i = 0
    while i < len(transcript):
        # Collect consecutive assistant messages (questions)
        batch_questions = []
        while i < len(transcript) and transcript[i].get("role") == "assistant":
            batch_questions.append(transcript[i]["content"])
            i += 1

        # Collect consecutive user messages (answers)
        batch_answers = []
        while i < len(transcript) and transcript[i].get("role") == "user":
            batch_answers.append(transcript[i]["content"])
            i += 1

        # Add the batch of questions and answers
        questions.extend(batch_questions)

        # Pad answers to match questions if necessary
        for j in range(len(batch_questions)):
            if j < len(batch_answers):
                answers.append(batch_answers[j])
            else:
                answers.append("未回答")

    # Pair questions with answers
    qa_pairs = []
    for q, a in zip(questions, answers):
        qa_pairs.append(f"Q: {q}\nA: {a}")

    qa_section = "\n\n".join(qa_pairs) if qa_pairs else "（質疑応答なし）"

    # Log for debugging
    logger.info(
        "regenerate_spec: Q&A pairing - questions=%d, answers=%d, pairs=%d",
        len(questions),
        len(answers),
        len(qa_pairs),
    )

    # Format attachments if provided
    attachments_section = ""
    if attachments:
        formatted_attachments = _format_attachments_for_prompt(attachments)
        if formatted_attachments:
            attachments_section = f"\n[添付ファイル情報]\n{formatted_attachments}\n"

    system = (
        "あなたは特許明細書の執筆専門家です。与えられた指示書を参考にしつつ、"
        "アイデア概要と質疑応答の内容から、完全な特許明細書を作成してください。"
    )

    prompt = (
        f"[作成の指針となる指示書]\n{instruction_md}\n\n"
        f"[発明のアイデア概要]\n{idea_description}\n\n"
        f"[ヒアリングによる追加情報]\n{qa_section}\n"
        f"{attachments_section}"
        "[重要な作成要件]\n"
        "- 指示書は作成の指針として参照し、指示書の文章そのものは出力に含めないこと\n"
        "- アイデア概要と質疑応答の情報を統合して、実際の特許明細書を作成すること\n"
        "- 前置きや挨拶は不要（本文のみを出力）\n"
    )

    # Add attachment-specific requirement if attachments exist
    if attachments:
        prompt += "- 添付ファイルの情報も適切に反映させること\n"

    # Add common requirements
    prompt += (
        "- 以下のセクションを含む完全な特許明細書を出力：\n"
        "  - 発明の名称\n"
        "  - 技術分野\n"
        "  - 背景技術\n"
        "  - 発明が解決しようとする課題\n"
        "  - 課題を解決するための手段\n"
        "  - 発明の効果\n"
        "  - 実施の形態\n"
        "  - 請求項（案）\n"
        "- 情報が不足している箇所は '未記載' または '（要確認）' と明記\n"
        "- Markdown形式で、読みやすく構造化して出力\n"
        "- 指示書のタイトルや本文をそのまま含めないこと\n"
    )

    model_name = _model_name()
    logger.info(
        (
            "regenerate_spec: calling model=%s, instruction_len=%d, "
            "idea_len=%d, qa_pairs=%d, gemini_files=%d"
        ),
        model_name,
        len(instruction_md or ""),
        len(idea_description or ""),
        len(qa_pairs),
        len(gemini_files or []),
    )

    # Build base contents so we can reuse across retries/models
    text_contents = f"{system}\n\n{prompt}"
    file_contents_base: Optional[List[Any]] = None
    if gemini_files:
        base: List[Any] = []
        for file_info in gemini_files:
            if isinstance(file_info, str):
                base.append(file_info)
            elif hasattr(file_info, "name"):
                base.append(file_info)
            else:
                logger.warning(f"Unsupported file format: {type(file_info)}")
        file_contents_base = base

    # Attempts: initial -> retry(same model) -> flash fallback
    attempts: List[Tuple[str, str]] = [
        (model_name, "initial"),
        (model_name, "retry"),
        ("gemini-2.5-flash", "flash_fallback"),
    ]

    last_error: Optional[Exception] = None
    for mdl, phase in attempts:
        if phase == "retry":
            # small backoff before retrying
            time.sleep(1.2)
            logger.info("regenerate_spec: retrying after 500 with same model")
        elif phase == "flash_fallback":
            logger.info("regenerate_spec: switching to gemini-2.5-flash after repeated 500s")
        try:
            if file_contents_base is not None:
                contents = list(file_contents_base)
                contents.append(text_contents)
                resp = client.models.generate_content(model=mdl, contents=contents)
            else:
                resp = client.models.generate_content(model=mdl, contents=text_contents)
            _log_response_debug("regenerate_spec", resp)
            text = _clean_llm_spec_text((getattr(resp, "text", "") or "").strip())
            if not text:
                error_msg = "APIから空の応答を受け取りました。再試行してください"
                logger.error("regenerate_spec: Empty response; using fallback skeleton.")
                return _fallback_skeleton(instruction_md, idea_description), error_msg
            return text, None
        except Exception as e:
            last_error = e
            if _is_internal_server_error(e):
                # If this was the initial attempt, allow retry; otherwise continue to next attempt
                logger.warning("regenerate_spec: 500 INTERNAL detected: %s", str(e)[:200])
                continue
            # Non-500 error: classify and fail fast
            error_msg = _classify_api_error(e)
            logger.exception("regenerate_spec: Gemini API error; using fallback skeleton.")
            return _fallback_skeleton(instruction_md, idea_description), error_msg

    # All attempts failed (likely repeated 500)
    error_msg = _classify_api_error(last_error) if last_error else "不明なエラー"
    logger.exception("regenerate_spec: Gemini API error after retries; using fallback skeleton.")
    return _fallback_skeleton(instruction_md, idea_description), error_msg


def _log_response_debug(operation: str, resp: Any) -> None:
    """Best-effort logging of useful response metadata without crashing."""
    try:
        finishes = []
        for cand in getattr(resp, "candidates", []) or []:
            finishes.append(getattr(cand, "finish_reason", None))
        prompt_feedback = getattr(resp, "prompt_feedback", None)
        block_reason = getattr(prompt_feedback, "block_reason", None) if prompt_feedback else None
        usage = getattr(resp, "usage_metadata", None)
        text_len = len(getattr(resp, "text", "") or "")
        logger.info(
            "%s: finish_reasons=%s block_reason=%s usage=%s text_len=%d",
            operation,
            finishes,
            block_reason,
            usage,
            text_len,
        )
    except Exception:
        logger.exception("%s: failed to inspect response", operation)


def _fallback_skeleton(instruction_md: str, idea_description: str) -> str:
    sections = _derive_sections_from_instruction(instruction_md)
    lines: List[str] = []
    lines.append("# 特許明細書草案")
    if idea_description.strip():
        first = idea_description.strip().splitlines()[0][:100]
        lines.append("")
        lines.append(f"> アイデア概要: {first}")
    for sec in sections or [
        "発明の名称",
        "技術分野",
        "背景技術",
        "発明が解決しようとする課題",
        "課題を解決するための手段",
        "発明の効果",
        "実施の形態",
        "産業上の利用可能性",
    ]:
        lines.append("")
        lines.append(f"## {sec}")
        lines.append("未記載")
    return "\n".join(lines)


def _derive_sections_from_instruction(instruction_md: str) -> List[str]:
    sections: List[str] = []
    seen = set()
    for raw in instruction_md.splitlines():
        line = raw.strip()
        m1 = re.match(r"^(?:#+)\s+(.+)$", line)
        m2 = re.match(r"^\d+\.\s+(.+)$", line)
        title = None
        if m1:
            title = m1.group(1).strip()
        elif m2:
            title = m2.group(1).strip()
        if title and title not in seen and 1 <= len(title) <= 50:
            seen.add(title)
            sections.append(title)
        if len(sections) >= 12:
            break
    return sections


def check_spec_completeness(
    instruction_md: str, current_spec_md: str, version: int
) -> tuple[bool, float]:
    """
    Check if the specification is complete enough to be finalized.

    Returns:
        tuple: (is_complete, score) where is_complete is True if ready to finalize,
               and score is a completeness percentage (0-100)
    """
    client = _get_client()
    if client is None:
        # Simple heuristic when API is unavailable
        has_placeholders = "未記載" in current_spec_md
        spec_length = len(current_spec_md)
        if not has_placeholders and spec_length > 3000:
            score = min(100, 70 + (spec_length - 3000) / 100)
            return score >= 85, score
        return False, 50.0 if has_placeholders else 60.0

    system = (
        "あなたは特許明細書の品質評価専門家です。指示書のチェックリストに基づいて、"
        "現在のドラフトの完成度を評価してください。"
    )
    prompt = (
        f"[指示書の最終チェックリスト]\n{instruction_md}\n\n"
        f"[現行ドラフト]\n{current_spec_md}\n\n"
        "[評価要件]\n"
        "以下の観点で0-100のスコアを1つだけ出力してください（数値のみ）：\n"
        "- 発明の本質が捉えられているか（20点）\n"
        "- 従来技術との差分が明確か（20点）\n"
        "- 実施可能要件を満たしているか（20点）\n"
        "- クレーム設計が適切か（20点）\n"
        "- 未記載箇所がないか（20点）\n"
    )

    try:
        model_name = _model_name()
        logger.info(
            "check_spec_completeness: calling model=%s, version=%d, draft_len=%d",
            model_name,
            version,
            len(current_spec_md or ""),
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=f"{system}\n\n{prompt}",
        )
        _log_response_debug("check_spec_completeness", resp)
        text = (resp.text or "").strip()

        # Extract numeric score safely
        m = re.search(r"\d+(?:\.\d+)?", text)
        if m:
            try:
                score = float(m.group())
                score = min(100, max(0, score))  # Clamp to 0-100
            except ValueError:
                logger.warning("check_spec_completeness: Could not parse score, using default")
                score = 70.0
        else:
            logger.warning("check_spec_completeness: Could not parse score, using default")
            score = 70.0

        is_complete = score >= 85
        return is_complete, score

    except Exception:
        logger.exception("check_spec_completeness: API error, using fallback")
        has_placeholders = "未記載" in current_spec_md
        spec_length = len(current_spec_md)
        if not has_placeholders and spec_length > 3000:
            score = min(100, 70 + (spec_length - 3000) / 100)
            return score >= 85, score
        return False, 50.0 if has_placeholders else 60.0


def generate_invention_description(
    instruction_md: str,
    invention_title: str,
    idea_description: str,
    transcript: List[Dict[str, str]] | None = None,
    attachments: Optional[List[Dict]] = None,
    gemini_files: Optional[List] = None,
) -> Tuple[str, Optional[str]]:
    """
    Generate a full-format Invention Description (発明説明書) based on the provided
    instruction Markdown, idea description, transcript (Q&A), and attachments.

    Returns Markdown text and optional user-friendly error message.
    """
    client = _get_client()

    # Build Q&A section (optional)
    qa_section = "（質疑応答なし）"
    if transcript:
        questions: List[str] = []
        answers: List[str] = []
        i = 0
        while i < len(transcript):
            q_batch: List[str] = []
            while i < len(transcript) and transcript[i].get("role") == "assistant":
                q_batch.append(transcript[i]["content"])
                i += 1
            a_batch: List[str] = []
            while i < len(transcript) and transcript[i].get("role") == "user":
                a_batch.append(transcript[i]["content"])
                i += 1
            questions.extend(q_batch)
            for j in range(len(q_batch)):
                answers.append(a_batch[j] if j < len(a_batch) else "未回答")
        pairs = [f"Q: {q}\nA: {a}" for q, a in zip(questions, answers)]
        qa_section = "\n\n".join(pairs) if pairs else qa_section

    # Format attachments (optional)
    attachments_section = ""
    if attachments:
        formatted_attachments = _format_attachments_for_prompt(attachments)
        if formatted_attachments:
            attachments_section = f"\n[添付ファイル情報]\n{formatted_attachments}\n"

    # System guidance matches the instruction's role
    system = (
        "あなたは企業の知財部に所属する熟練の弁理士です。"
        "与えられた『発明説明書（フルバージョン）生成』の指示を最優先で参照し、"
        "入力情報・アイデア概要・質疑応答・添付資料を総合して、発明説明書を作成してください。"
    )

    # Build the input information section as requested by the prompt
    input_info = (
        "**# 入力情報**\n"
        f"* **発明の名称案:** `{invention_title or '（未設定）'}`\n"
        f"* **この発明が解決したい課題（背景）:** 未記載（以下の概要・Q&Aから適宜補完）\n"
        f"* **基本的な解決手段（発明のコアアイデア）:** {idea_description.strip() or '未記載'}\n"
        f"* **想定される利用者や適用分野:** 未記載（以下の情報から推定可）\n"
        f"* **その他特記事項（あれば）:** 未記載（添付・Q&A参照）\n"
    )

    # Compose the full prompt
    prompt = (
        f"[発明説明書作成のための指示]\n{instruction_md}\n\n"
        f"{input_info}\n\n"
        f"[アイデアの詳細説明]\n{idea_description}\n\n"
        f"[ヒアリングQ&A]\n{qa_section}\n"
        f"{attachments_section}"
        "[出力要件]\n"
        "- 指示の章立て（0〜5）に従い、Markdownで出力\n"
        "- 前置きや挨拶は不要（本文のみ）\n"
        "- 情報が不足する箇所は '未記載' または '（要確認）' と明記\n"
    )

    # If no client, return a simple skeleton
    if client is None:
        logger.warning("generate_invention_description: No client; using fallback skeleton.")
        return _fallback_invention_skeleton(invention_title, idea_description), (
            "APIクライアントの初期化に失敗しました。APIキーの設定を確認してください"
        )

    model_name = _model_name()
    logger.info(
        (
            "generate_invention_description: model=%s, instr_len=%d, idea_len=%d, "
            "qa_len=%d, files=%d"
        ),
        model_name,
        len(instruction_md or ""),
        len(idea_description or ""),
        len(qa_section or ""),
        len(gemini_files or []),
    )

    contents_text = f"{system}\n\n{prompt}"

    try:
        if gemini_files:
            contents: List[Any] = []
            for f in gemini_files:
                if isinstance(f, str) or hasattr(f, "name"):
                    contents.append(f)
            contents.append(contents_text)
            resp = client.models.generate_content(model=model_name, contents=contents)
        else:
            resp = client.models.generate_content(model=model_name, contents=contents_text)
        _log_response_debug("generate_invention_description", resp)
        text = _clean_llm_spec_text((resp.text or "").strip())
        if not text:
            logger.error("generate_invention_description: empty response; using fallback.")
            return _fallback_invention_skeleton(invention_title, idea_description), (
                "APIから空の応答を受け取りました。再試行してください"
            )
        return text, None
    except Exception as e:
        logger.exception("generate_invention_description: API error; using fallback.")
        return (
            _fallback_invention_skeleton(invention_title, idea_description),
            _classify_api_error(e),
        )


def _fallback_invention_skeleton(title: str, idea_description: str) -> str:
    lines = []
    lines.append("# 発明説明書（ドラフト）")
    if title:
        lines.append("")
        lines.append(f"> 発明の名称案: {title}")
    if idea_description.strip():
        first = idea_description.strip().splitlines()[0][:100]
        lines.append(f"> アイデア概要: {first}")
    sections = [
        "0.【発明の名称}",
        "1.【発明が解決しようとする課題}",
        "2.【課題を解決するための手段}",
        "3.【発明の効果}",
        "4.【発明を実施するための形態】（実施例）",
        "5.【請求項】",
    ]
    for s in sections:
        lines.append("")
        lines.append(f"## {s}")
        lines.append("未記載")
    return "\n".join(lines)
