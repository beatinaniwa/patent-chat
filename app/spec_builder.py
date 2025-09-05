from __future__ import annotations

from typing import Dict, List

from app.state import Idea, Revision


def append_user_answer(transcript: List[Dict[str, str]], answer: str) -> None:
    transcript.append({"role": "user", "content": answer})


def append_assistant_message(transcript: List[Dict[str, str]], message: str) -> None:
    transcript.append({"role": "assistant", "content": message})


def add_revision(idea: Idea, revision: Revision, max_history: int = 50) -> None:
    """Add a revision to idea with history cap.

    Newest first ordering. Trims history to max_history items.
    """
    idea.revisions.insert(0, revision)
    # Trim to max_history
    if len(idea.revisions) > max_history:
        del idea.revisions[max_history:]
    idea.active_revision_id = revision.id
