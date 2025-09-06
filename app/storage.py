from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from .state import Idea, Revision

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
IDEAS_PATH = DATA_DIR / "ideas.json"
PROMPTS_PATH = DATA_DIR / "prompt_overrides.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not IDEAS_PATH.exists():
        IDEAS_PATH.write_text(
            json.dumps({"ideas": []}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    # Create prompt overrides file if missing (empty defaults)
    if not PROMPTS_PATH.exists():
        PROMPTS_PATH.write_text(
            json.dumps(
                {"spec_instruction_md": "", "invention_instruction_md": ""},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
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

        # Convert revisions if present
        revisions = obj.get("revisions") or []
        converted_revisions = []
        for rev in revisions:
            # created_at may be string
            if isinstance(rev.get("created_at"), str):
                try:
                    rev["created_at"] = datetime.fromisoformat(rev["created_at"])  # type: ignore[index]
                except Exception:
                    pass
            converted_revisions.append(Revision(**rev))
        obj["revisions"] = converted_revisions
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


def load_prompt_overrides() -> dict:
    """Load prompt overrides persisted in the data directory.

    Returns a dict with keys: spec_instruction_md, invention_instruction_md
    (empty strings if not set)
    """
    ensure_data_dir()
    try:
        raw = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
        spec_md = raw.get("spec_instruction_md") or ""
        inv_md = raw.get("invention_instruction_md") or ""
        return {"spec_instruction_md": spec_md, "invention_instruction_md": inv_md}
    except Exception:
        return {"spec_instruction_md": "", "invention_instruction_md": ""}


def save_prompt_overrides(spec_instruction_md: str, invention_instruction_md: str) -> None:
    """Persist prompt overrides to the data directory."""
    ensure_data_dir()
    payload = {
        "spec_instruction_md": spec_instruction_md or "",
        "invention_instruction_md": invention_instruction_md or "",
    }
    PROMPTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def get_idea(ideas: List[Idea], idea_id: str) -> Optional[Idea]:
    for i in ideas:
        if i.id == idea_id:
            return i
    return None


def delete_idea(ideas: List[Idea], idea_id: str) -> List[Idea]:
    return [i for i in ideas if i.id != idea_id]
