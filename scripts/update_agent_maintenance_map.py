#!/usr/bin/env python3
"""Generate a source-backed maintenance map; never infer scientific completion."""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "config/agent_maintenance_capabilities.json"
DEST = "docs/AGENT_MAINTENANCE_MAP.md"
BASE_URL = "https://github.com/Hu-py/research-opportunity-workbench"
TRACKED_PREFIXES = ("backend/", "frontend/", "skills/", "tests/", "scripts/", ".github/workflows/")
TRACKED_PATHS = ("pyproject.toml", "frontend/vercel.json", MANIFEST)

def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

def render(root: Path, data: dict) -> str:
    base = data["reviewed_commit"]
    files = set(git(root, "ls-files").splitlines())
    changes = set(git(root, "diff", "--name-only", base + "..HEAD", "--").splitlines())
    capabilities = data["capabilities"]
    tally = Counter(x["reviewed_state"] for x in capabilities)
    rows, flagged, mapped = [], [], set()

    for entry in capabilities:
        paths = entry["evidence_paths"]
        mapped.update(paths)
        present = [x for x in paths if x in files]
        touched = sorted(x for x in paths if x in changes)
        # All evidence paths are required for the simple code-presence check.
        if not paths:
            observed = "无已登记路径"
        elif len(present) == len(paths):
            observed = "路径均存在"
        elif present:
            observed = "部分路径存在"
        else:
            observed = "证据路径未出现"
        reviewed = entry["reviewed_state"]
        uncertain = bool(touched)
        uncertain |= reviewed == "已实现" and observed != "路径均存在"
        uncertain |= reviewed == "未实现" and observed == "路径均存在"
        marker = "需人工复核" if uncertain else "—"
        if uncertain:
            flagged.append((entry["id"], entry["name"], touched))
        references = "、".join(
            "[`{}`]({}/blob/main/{})".format(p, BASE_URL, p) if p in files
            else "`{}`（不存在）".format(p)
            for p in paths
        ) or "—"
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            entry["id"], entry["name"], reviewed, observed, marker, references
        ))

    changed_other = sorted(
        x for x in changes if x not in mapped and x != DEST and
        (x.startswith(TRACKED_PREFIXES) or x in TRACKED_PATHS)
    )
    skills = sorted(x for x in files if x.startswith("skills/") and x.endswith("/SKILL.md"))
    workflows = sorted(x for x in files if x.startswith(".github/workflows/") and x.endswith((".yml", ".yaml")))

    lines = [
        "# Agent Maintenance Map｜Research Atlas（自动维护）",
        "",
        "> 人工核验基准：{}，提交 `{}`。".format(data["reviewed_date"], base[:12]),
        "> **自动更新的是文件存在性和变更提醒，不是能力已完成的科研判断。**",
        "",
        "## 状态概览",
        "",
        "- {} 项能力；人工核验：**已实现 {}**、**部分实现 {}**、**未实现 {}**。".format(
            len(capabilities), tally["已实现"], tally["部分实现"], tally["未实现"]),
        "- 自动发现 **{} 个 Skills**、**{} 个 GitHub Actions 工作流**。".format(len(skills), len(workflows)),
        "- 自上次人工核验以来，**{} 项能力需复核**。".format(len(flagged)),
        "",
        "## 能力地图",
        "",
        "| 编号 | 能力 | 人工核验状态 | 自动检测 | 变更提示 | 相关源文件 |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        "## 待复核改动",
        "",
    ]
    if flagged:
        for ident, name, touched in flagged:
            reason = "、".join("`{}`".format(x) for x in touched) if touched else "代码路径与已审核结论不一致"
            lines.append("- **{} {}**：{}".format(ident, name, reason))
    else:
        lines.append("- 暂无被映射能力的变更。")

    lines += ["", "### 尚未映射的相关改动", ""]
    lines += ["- `{}`".format(x) for x in changed_other[:50]] or ["- 暂无。"]
    if len(changed_other) > 50:
        lines.append("- 另有 {} 项未展示。".format(len(changed_other)-50))
    lines += [
        "", "## 当前 Skills 与工作流", "",
        "**Skills**：{}".format("、".join("`{}`".format(x.split("/")[1]) for x in skills) or "暂无"),
        "",
        "**工作流**：{}".format("、".join("`{}`".format(x.rsplit("/", 1)[-1]) for x in workflows) or "暂无"),
        "",
        "## 当前建设优先级",
        "",
        "- **P0-A**：临时研究任务输入与独立检索配置。",
        "- **P0-B**：动态主题—子类的研究分类。",
        "- **P0-C**：重点文献、相关文献和待确定问题的 Research Brief。",
        "- **P1**：三个专业 Agent、个人画像与跨 Agent 知识共享。",
        "",
        "## 维护规则",
        "",
        "1. 提交或合并代码至 `main` 后，GitHub Actions 自动生成本文件。",
        "2. 自动检测只标记源代码路径和变动；**不自动把部分实现升级为已实现**。",
        "3. 审核者应在 Pull Request 中修改 `config/agent_maintenance_capabilities.json` 的人工状态、证据路径、核验日期及基准提交。",
        "4. 运行是否成功以具体 GitHub Actions run 和真实科研评测为准，不以文件存在代替验证。",
        "5. 代码变更通过 GitHub PR/commit 追溯，开发计划仍以 [dev-tracker]({}/tree/main/dev-tracker) 追踪。".format(BASE_URL),
        "",
        "_本地图的状态不是 GPT 自动给出的完成证明。_",
        "",
    ]
    return "\n".join(lines)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the map needs regeneration")
    args = parser.parse_args()
    manifest = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    content = render(ROOT, manifest)
    target = ROOT / DEST
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise SystemExit("Maintenance map is stale")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print("Updated", DEST)

if __name__ == "__main__":
    main()
