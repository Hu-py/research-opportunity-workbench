"""Load trusted, versioned research skills from the repository."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills"
ALLOWED = (
    "paper_reader", "method_transfer", "idea_discovery", "idea_critic",
    "research_profile", "literature_discovery",
)
REGISTERED = ALLOWED


def load_skills(names=ALLOWED) -> str:
    parts = []
    for name in names:
        if name not in REGISTERED:
            raise ValueError("Unknown research skill")
        file = ROOT / name / "SKILL.md"
        if file.exists():
            parts.append("### " + name + "\n" + file.read_text(encoding="utf-8")[:7000])
    return "\n\n".join(parts)
