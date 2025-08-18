from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

from google import genai

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


def _title_model_name() -> str:
    # タイトル生成は軽量・高速な flash を既定とする
    return os.getenv("GEMINI_TITLE_MODEL", "gemini-2.5-flash")


def _get_client() -> Optional[genai.Client]:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    try:
        if not api_key:
            logger.warning("Gemini API key is not set (GOOGLE_API_KEY or GEMINI_API_KEY).")
            return None
        return genai.Client(api_key=api_key)
    except Exception:
        logger.exception("Failed to initialize Gemini client.")
        return None


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


def bootstrap_spec(sample_manual_md: str, idea_description: str) -> str:
    client = _get_client()
    if client is None:
        logger.warning("bootstrap_spec: No client; generating fallback skeleton.")
        return _fallback_skeleton(sample_manual_md, idea_description)
    system = (
        "あなたは特許明細書の下書きを作る専門家です。与えられた指示書（プロンプト）を最優先で参照し、"
        "不足部分は'未記載'と明示しつつ、Markdownで初稿を作ってください。"
    )
    prompt = (
        f"[指示書]\n{sample_manual_md}\n\n"
        f"[アイデア概要]\n{idea_description}\n\n"
        "[出力要件]\n- 見出しは手順書の順序に従う\n- 箇条書き可\n- 未確定箇所は '未記載' と記す\n"
    )
    try:
        model_name = _model_name()
        logger.info(
            "bootstrap_spec: calling model=%s, instruction_len=%d, idea_len=%d",
            model_name,
            len(sample_manual_md or ""),
            len(idea_description or ""),
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=f"{system}\n\n{prompt}",
        )
        _log_response_debug("bootstrap_spec", resp)
        text = (resp.text or "").strip()
        if not text:
            logger.error("bootstrap_spec: Empty response text; using fallback skeleton.")
            return _fallback_skeleton(sample_manual_md, idea_description)
        return text
    except Exception:
        logger.exception("bootstrap_spec: Gemini API error; using fallback skeleton.")
        return _fallback_skeleton(sample_manual_md, idea_description)


def next_questions(
    instruction_md: str,
    transcript: List[Dict[str, str]],
    current_spec_md: str,
    num_questions: int = 3,
    version: int = 1,
    is_final: bool = False,
) -> List[str]:
    # Don't generate questions if already finalized or at version 5
    if is_final or version >= 5:
        return []

    client = _get_client()
    if client is None:
        return [
            "現行ドラフトに未記載箇所があります。図面は必要ですか？（はい/いいえ）",
            "実施例は複数のバリエーションがありますか？（はい/いいえ）",
            "発明の効果に定量的根拠はありますか？（はい/いいえ）",
        ][:num_questions]

    transcript_str = "\n".join([f"{m['role']}: {m['content']}" for m in transcript][-20:])
    system = (
        "あなたは特許明細書の執筆アシスタントです。以下の指示書に照らして、"
        "現行ドラフトの不足・曖昧・未記載部分を見つけ、ユーザーが答えやすい"
        "『はい/いいえ』のクローズド質問を優先度順に作成してください。"
    )
    prompt = (
        f"[指示書]\n{instruction_md}\n\n"
        f"[現行ドラフト(Markdown)]\n{current_spec_md}\n\n"
        f"[これまでの対話]\n{transcript_str}\n\n"
        "[出力要件]\n"
        "- 質問のみを出力（前置きや挨拶は不要）\n"
        "- 各行1問、{num}問\n"
        "- はい/いいえ で答えられる形式（例: '〜ですか？（はい/いいえ）'）\n"
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
    except Exception:
        logger.exception("next_questions: Gemini API error; using canned questions.")
        return [
            "課題の技術的背景は十分に記載されていますか？（はい/いいえ）",
            "構成要件の必須/任意が明確ですか？（はい/いいえ）",
            "変形例はありますか？（はい/いいえ）",
        ][:num_questions]
    lines = [line.strip("- ") for line in text.splitlines() if line.strip()]
    return [line for line in lines if line][:num_questions]


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
        "出力は更新後のMarkdown全文のみ。"
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
        text = (resp.text or "").strip()
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
) -> str:
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
        logger.warning("regenerate_spec: No client; generating fallback skeleton.")
        return _fallback_skeleton(instruction_md, idea_description)

    # Format Q&A history for better understanding
    qa_pairs = []
    i = 0
    while i < len(transcript):
        if i < len(transcript) and transcript[i].get("role") == "assistant":
            question = transcript[i]["content"]
            answer = "未回答"
            if i + 1 < len(transcript) and transcript[i + 1].get("role") == "user":
                answer = transcript[i + 1]["content"]
                i += 2
            else:
                i += 1
            qa_pairs.append(f"Q: {question}\nA: {answer}")
        else:
            i += 1

    qa_section = "\n\n".join(qa_pairs) if qa_pairs else "（質疑応答なし）"

    system = (
        "あなたは特許明細書の専門家です。与えられた指示書、アイデア概要、および質疑応答の内容を総合的に考慮し、"
        "完全で一貫性のある特許明細書を作成してください。"
    )

    prompt = (
        f"[指示書]\n{instruction_md}\n\n"
        f"[アイデア概要]\n{idea_description}\n\n"
        f"[質疑応答による追加情報]\n{qa_section}\n\n"
        "[作成要件]\n"
        "- 上記の全ての情報を統合して、完全な特許明細書を作成\n"
        "- 指示書の構成に従い、各セクションを体系的に記述\n"
        "- アイデア概要を基礎とし、質疑応答で得られた情報を適切に反映\n"
        "- 未確定箇所は '未記載' と明記\n"
        "- Markdown形式で出力\n"
    )

    try:
        model_name = _model_name()
        logger.info(
            "regenerate_spec: calling model=%s, instruction_len=%d, idea_len=%d, qa_pairs=%d",
            model_name,
            len(instruction_md or ""),
            len(idea_description or ""),
            len(qa_pairs),
        )
        resp = client.models.generate_content(
            model=model_name,
            contents=f"{system}\n\n{prompt}",
        )
        _log_response_debug("regenerate_spec", resp)
        text = (resp.text or "").strip()
        if not text:
            logger.error("regenerate_spec: Empty response; using fallback skeleton.")
            return _fallback_skeleton(instruction_md, idea_description)
        return text
    except Exception:
        logger.exception("regenerate_spec: Gemini API error; using fallback skeleton.")
        return _fallback_skeleton(instruction_md, idea_description)


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
    # Version 5 is always final
    if version >= 5:
        return True, 100.0

    # For earlier versions, check quality
    client = _get_client()
    if client is None:
        # If no client, use simple heuristics
        has_placeholders = "未記載" in current_spec_md
        spec_length = len(current_spec_md)
        # Simple scoring: no placeholders and reasonable length
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

        # Extract numeric score
        try:
            score = float(re.search(r'\d+(?:\.\d+)?', text).group())
            score = min(100, max(0, score))  # Clamp to 0-100
        except (AttributeError, ValueError):
            logger.warning("check_spec_completeness: Could not parse score, using default")
            score = 70.0

        # Consider complete if score >= 85
        is_complete = score >= 85
        return is_complete, score

    except Exception:
        logger.exception("check_spec_completeness: API error, using fallback")
        # Fallback: check for placeholders and length
        has_placeholders = "未記載" in current_spec_md
        spec_length = len(current_spec_md)
        if not has_placeholders and spec_length > 3000:
            score = min(100, 70 + (spec_length - 3000) / 100)
            return score >= 85, score
        return False, 50.0 if has_placeholders else 60.0
