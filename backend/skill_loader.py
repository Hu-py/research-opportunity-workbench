"""Read versioned instruction-only research skills from the trusted repository."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "skills"
ALLOWED = ("paper_reader","method_transfer","idea_critic")

def load_skills(names=ALLOWED) -> str:
    parts=[]
    for name in names:
        if name not in ALLOWED:raise ValueError("Unknown research skill")
        file=ROOT/name/"SKILL.md"
        if not file.exists():continue
        parts.append("### "+name+"\n"+file.read_text(encoding="utf-8")[:4500])
    return "\n\n".join(parts)
