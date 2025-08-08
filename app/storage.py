from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from .state import Idea

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IDEAS_PATH = DATA_DIR / "ideas.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not IDEAS_PATH.exists():
        IDEAS_PATH.write_text(
            json.dumps({"ideas": []}, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_ideas() -> List[Idea]:
    ensure_data_dir()
    raw = json.loads(IDEAS_PATH.read_text(encoding="utf-8"))
    ideas: List[Idea] = []
    for obj in raw.get("ideas", []):
        ideas.append(Idea(**obj))
    return ideas


def save_ideas(ideas: List[Idea]) -> None:
    ensure_data_dir()
    payload = {"ideas": [asdict(i) for i in ideas]}
    IDEAS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_idea(ideas: List[Idea], idea_id: str) -> Optional[Idea]:
    for i in ideas:
        if i.id == idea_id:
            return i
    return None


def delete_idea(ideas: List[Idea], idea_id: str) -> List[Idea]:
    return [i for i in ideas if i.id != idea_id]
