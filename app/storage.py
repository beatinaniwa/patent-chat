from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

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
        # Convert datetime strings back to datetime objects in attachments
        attachments = obj.get("attachments") or []
        converted_attachments = []
        for attachment_dict in attachments:
            if "upload_time" in attachment_dict and isinstance(attachment_dict["upload_time"], str):
                attachment_dict["upload_time"] = datetime.fromisoformat(
                    attachment_dict["upload_time"]
                )
            # Import Attachment here to avoid circular import issues
            from .state import Attachment

            converted_attachments.append(Attachment(**attachment_dict))
        obj["attachments"] = converted_attachments
        ideas.append(Idea(**obj))
    return ideas


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def save_ideas(ideas: List[Idea]) -> None:
    ensure_data_dir()
    payload = {"ideas": [asdict(i) for i in ideas]}
    IDEAS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, cls=DateTimeEncoder), encoding="utf-8"
    )


def get_idea(ideas: List[Idea], idea_id: str) -> Optional[Idea]:
    for i in ideas:
        if i.id == idea_id:
            return i
    return None


def delete_idea(ideas: List[Idea], idea_id: str) -> List[Idea]:
    return [i for i in ideas if i.id != idea_id]
