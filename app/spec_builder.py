from __future__ import annotations

from typing import Dict, List


def append_user_answer(transcript: List[Dict[str, str]], answer: str) -> None:
    transcript.append({"role": "user", "content": answer})


def append_assistant_message(transcript: List[Dict[str, str]], message: str) -> None:
    transcript.append({"role": "assistant", "content": message})
