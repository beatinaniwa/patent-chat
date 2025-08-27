from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Attachment:
    filename: str
    content_base64: str
    comment: str
    file_type: str
    upload_time: datetime = field(default_factory=datetime.now)
    gemini_file_id: Optional[str] = None
    gemini_mime_type: Optional[str] = None


@dataclass
class Idea:
    id: str
    title: str
    category: str
    description: str
    # Conversation turns for hearing
    messages: List[Dict[str, str]] = field(default_factory=list)
    # Draft specification text (Markdown)
    draft_spec_markdown: str = ""
    # Draft version counter (1 = 初版)
    draft_version: int = 1
    # Whether this specification is finalized
    is_final: bool = False
    # Attached files
    attachments: List[Attachment] = field(default_factory=list)


@dataclass
class AppState:
    # Selected idea id in sidebar
    selected_idea_id: Optional[str] = None
    # UI: new idea form visibility
    show_new_idea_form: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)
