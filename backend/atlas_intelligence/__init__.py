"""Research Atlas research-signal pipeline (separate from legacy Radar A/B)."""

from .sources import SOURCE_GROUPS, assign_source_groups, load_source_plan
from .signals import build_research_brief, render_research_brief

__all__ = [
    "SOURCE_GROUPS", "assign_source_groups", "load_source_plan",
    "build_research_brief", "render_research_brief",
]
