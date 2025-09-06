from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from app.llm import DEFAULT_MODEL_NAME


@dataclass
class Attachment:
    filename: str
    content_base64: str
    comment: str
    file_type: str
    upload_time: datetime = field(default_factory=datetime.now)
    gemini_file_id: Optional[str] = None
    gemini_mime_type: Optional[str] = None
    # Store extracted text to avoid re-parsing (especially for PDFs)
    extracted_text: Optional[str] = None


@dataclass
class Revision:
    """A single LLM-applied refinement to a document.

    Stores the full refined text and metadata for history / export.
    """

    id: str
    created_at: datetime = field(default_factory=datetime.now)
    doc_type: str = "spec"  # "spec" or "explanation"
    feedback: str = ""
    text: str = ""
    diff: str = ""
    model: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)


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
    # Invention description (発明説明書 フルバージョン) Markdown
    invention_description_markdown: str = ""
    # Draft version counter (1 = 初版)
    draft_version: int = 1
    # Whether this specification is finalized
    is_final: bool = False
    # Attached files
    attachments: List[Attachment] = field(default_factory=list)
    # Latest completeness score (0-100), informational only
    completeness_score: float = 0.0
    # Refinement history (latest first)
    revisions: List[Revision] = field(default_factory=list)
    # Currently selected revision id (optional)
    active_revision_id: Optional[str] = None


@dataclass
class AppState:
    # Selected idea id in sidebar
    selected_idea_id: Optional[str] = None
    # UI: new idea form visibility
    show_new_idea_form: bool = False
    # UI: prompt editor visibility
    show_prompt_editor: bool = False
    # Selected Gemini model (e.g., gemini-2.5-pro or gemini-2.5-flash)
    gemini_model: str = DEFAULT_MODEL_NAME

    # Custom prompt overrides (session-level; present ⇒ always used)
    custom_spec_prompt: str = ""
    custom_invention_prompt: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)
