from __future__ import annotations

import os
from typing import List, Dict

import google.generativeai as genai


MODEL_NAME = "gemini-2.5-pro"


def _configure() -> None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("環境変数 GOOGLE_API_KEY が未設定です。")
    genai.configure(api_key=api_key)


def generate_title(idea_description: str) -> str:
    _configure()
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = (
        "以下のアイデア概要から、特許明細書草案用の簡潔な日本語タイトルを1つ生成してください。\n"
        "出力はタイトルのみ。\n\n"
        f"アイデア概要:\n{idea_description}"
    )
    resp = model.generate_content(prompt)
    return (resp.text or "タイトル")[:120]


def bootstrap_spec(sample_manual_md: str, idea_description: str) -> str:
    _configure()
    model = genai.GenerativeModel(MODEL_NAME)
    system = (
        "あなたは特許明細書の下書きを作る専門家です。与えられた手順書を参照して、"
        "不足部分は'未記載'と明示しつつ、Markdownで初稿を作ってください。"
    )
    prompt = (
        f"[手順書]\n{sample_manual_md}\n\n"
        f"[アイデア概要]\n{idea_description}\n\n"
        "[出力要件]\n- 見出しは手順書の順序に従う\n- 箇条書き可\n- 未確定箇所は '未記載' と記す\n"
    )
    resp = model.generate_content([system, prompt])
    return resp.text or ""


def next_questions(sample_manual_md: str, transcript: List[Dict[str, str]], num_questions: int = 3) -> List[str]:
    _configure()
    model = genai.GenerativeModel(MODEL_NAME)
    transcript_str = "\n".join([f"{m['role']}: {m['content']}" for m in transcript][-20:])
    prompt = (
        "特許明細書作成に必要な不足情報を特定し、はい/いいえ中心のクローズド質問を出してください。\n"
        f"手順書: \n{sample_manual_md}\n\n"
        f"これまでの対話: \n{transcript_str}\n\n"
        f"{num_questions}個の質問を、各行1問で出力してください。"
    )
    resp = model.generate_content(prompt)
    text = resp.text or ""
    lines = [l.strip("- ") for l in text.splitlines() if l.strip()]
    return [l for l in lines if l][:num_questions]


def refine_spec(sample_manual_md: str, transcript: List[Dict[str, str]], current_spec_md: str) -> str:
    _configure()
    model = genai.GenerativeModel(MODEL_NAME)
    transcript_str = "\n".join([f"{m['role']}: {m['content']}" for m in transcript][-30:])
    prompt = (
        "対話で得られた情報を既存ドラフトに反映して改善してください。\n"
        f"手順書:\n{sample_manual_md}\n\n"
        f"対話:\n{transcript_str}\n\n"
        f"現行ドラフト(Markdown):\n{current_spec_md}\n\n"
        "出力は更新後のMarkdown全文のみ。"
    )
    resp = model.generate_content(prompt)
    return resp.text or current_spec_md


