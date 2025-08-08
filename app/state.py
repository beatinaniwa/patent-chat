from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


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


@dataclass
class AppState:
    # Selected idea id in sidebar
    selected_idea_id: Optional[str] = None
    # UI: new idea form visibility
    show_new_idea_form: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


