from __future__ import annotations

import os
from typing import Dict, List, Optional

from google import genai

DEFAULT_MODEL_NAME = "gemini-2.5-pro"


def _model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)


def _title_model_name() -> str:
    # タイトル生成は軽量・高速な flash を既定とする
    return os.getenv("GEMINI_TITLE_MODEL", "gemini-2.5-flash")


def _get_client() -> Optional[genai.Client]:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    try:
        return genai.Client(api_key=api_key) if api_key else None
    except Exception:
        return None


def generate_title(idea_description: str) -> str:
    client = _get_client()
    if client is None:
        return (idea_description.strip().splitlines()[0] or "新規アイデア")[:30]
    prompt = (
        "以下のアイデア概要から、特許明細書草案用の簡潔な日本語タイトルを1つ生成してください。\n"
        "出力はタイトルのみ。\n\n"
        f"アイデア概要:\n{idea_description}"
    )
    try:
        resp = client.models.generate_content(
            model=_title_model_name(),
            contents=prompt,
        )
        return (resp.text or "タイトル")[:120]
    except Exception:
        return (idea_description.strip().splitlines()[0] or "新規アイデア")[:30]


def bootstrap_spec(sample_manual_md: str, idea_description: str) -> str:
    client = _get_client()
    if client is None:
        return "# 特許明細書草案 (未記載)\n\n- APIキー未設定のため自動生成をスキップしました。"
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
        resp = client.models.generate_content(
            model=_model_name(),
            contents=f"{system}\n\n{prompt}",
        )
        return resp.text or ""
    except Exception:
        return "# 特許明細書草案 (生成失敗)\n\n- 自動生成でエラーが発生しました。"


def next_questions(
    instruction_md: str,
    transcript: List[Dict[str, str]],
    current_spec_md: str,
    num_questions: int = 3,
) -> List[str]:
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
        "- 各行1問、{num}問\n"
        "- はい/いいえ で答えられる形式（例: '〜ですか？（はい/いいえ）'）\n"
        "- 1つの質問につき1論点、具体的に\n"
        "- 既に回答済みの重複質問は避ける\n".replace("{num}", str(num_questions))
    )
    try:
        resp = client.models.generate_content(
            model=_model_name(),
            contents=f"{system}\n\n{prompt}",
        )
        text = resp.text or ""
    except Exception:
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
        resp = client.models.generate_content(
            model=_model_name(),
            contents=prompt,
        )
        return resp.text or current_spec_md
    except Exception:
        return current_spec_md
