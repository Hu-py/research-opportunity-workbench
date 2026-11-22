"""Load versioned, allow-listed research Skills from the trusted repository."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills"
ALLOWED = ("literature_discovery", "paper_reader", "method_transfer",
           "cross_paper_synthesis", "report_templates", "idea_discovery",
           "idea_critic", "research_opportunity")
REGISTERED = ALLOWED + ("research_profile",)


def load_skills(names=ALLOWED) -> str:
    parts = []
    for name in names:
        if name not in REGISTERED:
            raise ValueError("Unknown research skill")
        file = ROOT / name / "SKILL.md"
        if not file.exists():
            continue
        parts.append("### " + name + "\n" + file.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
