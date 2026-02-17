#!/usr/bin/env python3
"""
devtracker.py - GitHub-centric dev tracker for terrain40k

Usage:
    python tools/devtracker.py status
    python tools/devtracker.py issues [--label bug|enhancement|task]
    python tools/devtracker.py add <bug|feat|task> <title> [--body TEXT]
    python tools/devtracker.py close <number> [--comment TEXT]
    python tools/devtracker.py sync
    python tools/devtracker.py validate
    python tools/devtracker.py build [--out PATH]
    python tools/devtracker.py milestone <version>
"""

import argparse
import ast
import json
import os
import py_compile
import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = REPO_ROOT / "addon" / "terrain40k"
STATE_FILE = REPO_ROOT / "docs" / "PROJECT_STATE.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
CONFIG_FILE = Path(__file__).resolve().parent / ".devtracker.json"
DEFAULT_REPO = "H9Lelouch/terrain40k"

LABEL_MAP = {"bug": "bug", "feat": "enhancement", "task": "task"}
TITLE_PREFIX = {"bug": "[BUG] ", "feat": "[FEAT] ", "task": "[TASK] "}

BUG_BODY = """\
## Context
- **Addon Version**: {version}
- **Blender Version**: (fill in)
- **OS**: Windows 11

## Expected Behavior
(describe)

## Actual Behavior
(describe)

## Reproduction Steps
1. (steps)

## Definition of Done
- [ ] Bug no longer reproducible
- [ ] Generated mesh passes manifold check
"""

FEAT_BODY = """\
## Proposed Feature
{title}

## Definition of Done
- [ ] Feature implemented and generating correct geometry
- [ ] Mesh is manifold / watertight
- [ ] UI properties added to panel
- [ ] PROJECT_STATE.md updated
- [ ] CHANGELOG.md entry added
"""

TASK_BODY = """\
## Description
{title}

## Definition of Done
- [ ] Implementation complete
- [ ] No regressions in existing module generators
- [ ] PROJECT_STATE.md updated if applicable
"""

BODY_TEMPLATES = {"bug": BUG_BODY, "feat": FEAT_BODY, "task": TASK_BODY}


# ── Error handling ─────────────────────────────────────────────────────────

class DevTrackerError(Exception):
    pass


def fail(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ── ANSI colors ────────────────────────────────────────────────────────────

def _use_color():
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def color(text, code):
    if _use_color():
        return f"\033[{code}m{text}\033[0m"
    return text


def green(t):
    return color(t, "32")


def red(t):
    return color(t, "31")


def yellow(t):
    return color(t, "33")


def cyan(t):
    return color(t, "36")


def bold(t):
    return color(t, "1")


# ── Utilities ──────────────────────────────────────────────────────────────

def gh_run(cmd_args, json_output=True):
    """Run a gh CLI command. Returns parsed JSON or raw string."""
    full_cmd = ["gh"] + cmd_args
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise DevTrackerError(
            "gh CLI not found. Install from https://cli.github.com/"
        )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise DevTrackerError(f"gh failed: {' '.join(full_cmd)}\n{stderr}")
    out = result.stdout.strip()
    if json_output and out:
        return json.loads(out)
    return out


def get_config():
    defaults = {"repo": DEFAULT_REPO, "default_milestone": None, "last_sync": None}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            stored = json.load(f)
        defaults.update(stored)
    return defaults


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_bl_info_version():
    """Extract version string from bl_info in __init__.py."""
    init_path = ADDON_DIR / "__init__.py"
    if not init_path.exists():
        return None
    with open(init_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    if isinstance(node.value, ast.Dict):
                        for key, val in zip(node.value.keys, node.value.values):
                            if (
                                isinstance(key, ast.Constant)
                                and key.value == "version"
                                and isinstance(val, ast.Tuple)
                            ):
                                return ".".join(str(e.value) for e in val.elts)
    return None


def get_last_commit():
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H|%s|%ci"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        return {"hash": "?", "subject": "?", "date": "?"}
    parts = result.stdout.strip().split("|", 2)
    if len(parts) < 3:
        return {"hash": "?", "subject": "?", "date": "?"}
    return {"hash": parts[0][:8], "subject": parts[1], "date": parts[2][:10]}


def count_checkboxes(text):
    """Returns (checked, total) from markdown checkboxes."""
    total = len(re.findall(r"- \[.?\]", text))
    checked = len(re.findall(r"- \[x\]", text, re.IGNORECASE))
    return checked, total


def get_latest_tag():
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


# ── Commands ───────────────────────────────────────────────────────────────

def cmd_status(args):
    cfg = get_config()
    repo = cfg["repo"]
    version = get_bl_info_version() or "unknown"
    commit = get_last_commit()

    print(bold(f"terrain40k  v{version}"))
    print(
        f"Last commit: {cyan(commit['hash'])} "
        f'"{commit["subject"]}"  ({commit["date"]})'
    )
    print()

    # Open issues by label
    try:
        issues = gh_run([
            "issue", "list", "--repo", repo, "--state", "open",
            "--json", "number,title,labels", "--limit", "200",
        ])
    except DevTrackerError as e:
        print(yellow(f"Could not fetch issues: {e}"))
        issues = []

    label_counts = {"bug": 0, "enhancement": 0, "task": 0, "other": 0}
    for issue in issues:
        labels = [lb["name"] for lb in issue.get("labels", [])]
        matched = False
        for lbl in labels:
            if lbl in label_counts:
                label_counts[lbl] += 1
                matched = True
        if not matched:
            label_counts["other"] += 1

    print(bold("Open Issues"))
    for lbl, cnt in label_counts.items():
        if cnt > 0:
            c = red(str(cnt)) if lbl == "bug" else str(cnt)
            print(f"  {lbl:<14} {c}")
    if not any(label_counts.values()):
        print(f"  {green('No open issues')}")
    print()

    # Milestones
    try:
        milestones = gh_run(["api", f"repos/{repo}/milestones"])
        if milestones:
            print(bold("Milestones"))
            for ms in milestones[:5]:
                title = ms["title"]
                opn = ms["open_issues"]
                closed = ms["closed_issues"]
                total = opn + closed
                pct = int(closed / total * 100) if total > 0 else 0
                bar_len = 20
                filled = int(bar_len * pct / 100)
                bar = "#" * filled + "-" * (bar_len - filled)
                print(f"  {title:<12} [{bar}] {closed}/{total} ({pct}%)")
            print()
    except DevTrackerError:
        pass

    # Feature completion from PROJECT_STATE
    if STATE_FILE.exists():
        content = STATE_FILE.read_text(encoding="utf-8")
        # Extract "Implemented Features" section
        match = re.search(
            r"## Implemented Features\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if match:
            checked, total = count_checkboxes(match.group(1))
            pct = int(checked / total * 100) if total > 0 else 0
            print(bold("Feature Completion") + " (PROJECT_STATE.md)")
            print(f"  {checked}/{total} features implemented ({pct}%)")


def cmd_issues(args):
    cfg = get_config()
    repo = cfg["repo"]
    cmd = [
        "issue", "list", "--repo", repo, "--state", "open",
        "--json", "number,title,labels,assignees,milestone,createdAt",
        "--limit", str(args.limit),
    ]
    if args.label:
        cmd.extend(["--label", args.label])

    issues = gh_run(cmd)
    if not issues:
        print(green("No open issues found."))
        return

    # Table header
    print(f"{'#':<5} {'Title':<45} {'Labels':<16} {'Milestone':<12} {'Assignees'}")
    print("-" * 95)
    for issue in issues:
        num = str(issue["number"])
        title = issue["title"][:44]
        labels = ",".join(lb["name"] for lb in issue.get("labels", []))[:15]
        ms = ""
        if issue.get("milestone"):
            ms = issue["milestone"].get("title", "")[:11]
        assignees = ",".join(
            a.get("login", "") for a in issue.get("assignees", [])
        )[:15] or "-"
        print(f"{num:<5} {title:<45} {labels:<16} {ms:<12} {assignees}")


def cmd_add(args):
    cfg = get_config()
    repo = cfg["repo"]
    version = get_bl_info_version() or "unknown"

    label = LABEL_MAP[args.type]
    title = TITLE_PREFIX[args.type] + args.title

    if args.body:
        body = args.body
    else:
        template = BODY_TEMPLATES[args.type]
        body = template.format(version=version, title=args.title)

    cmd = [
        "issue", "create", "--repo", repo,
        "--title", title,
        "--label", label,
        "--body", body,
    ]

    if not args.no_milestone and cfg.get("default_milestone"):
        cmd.extend(["--milestone", cfg["default_milestone"]])

    result = gh_run(cmd, json_output=False)
    print(green(f"Created issue: {result}"))


def cmd_close(args):
    cfg = get_config()
    repo = cfg["repo"]

    # Get issue title first
    issue = gh_run([
        "issue", "view", str(args.number), "--repo", repo,
        "--json", "title,state",
    ])
    title = issue.get("title", f"#{args.number}")

    if issue.get("state") == "CLOSED":
        print(yellow(f"Issue #{args.number} is already closed: {title}"))
        return

    if args.comment:
        gh_run(
            ["issue", "comment", str(args.number), "--repo", repo,
             "--body", args.comment],
            json_output=False,
        )

    gh_run(
        ["issue", "close", str(args.number), "--repo", repo],
        json_output=False,
    )
    print(green(f"Closed #{args.number}: {title}"))


def cmd_sync(args):
    cfg = get_config()
    repo = cfg["repo"]

    if not STATE_FILE.exists():
        fail(f"PROJECT_STATE.md not found at {STATE_FILE}")

    content = STATE_FILE.read_text(encoding="utf-8")
    original = content
    changes = []

    # 1) Sync Known Issues from open bug issues
    try:
        bug_issues = gh_run([
            "issue", "list", "--repo", repo, "--state", "open",
            "--label", "bug",
            "--json", "number,title",
            "--limit", "100",
        ])
    except DevTrackerError:
        bug_issues = []

    new_bugs = _format_known_issues(bug_issues)
    content = _replace_section(content, "Known Issues / Bugs", new_bugs)
    if "Known Issues / Bugs" in original and new_bugs.strip() != _extract_section(original, "Known Issues / Bugs").strip():
        changes.append(f"Updated Known Issues ({len(bug_issues)} open bugs)")

    # 2) Sync roadmap checkboxes from closed enhancement issues
    try:
        closed_feats = gh_run([
            "issue", "list", "--repo", repo, "--state", "closed",
            "--label", "enhancement",
            "--json", "number,title",
            "--limit", "200",
        ])
    except DevTrackerError:
        closed_feats = []

    if closed_feats:
        content, roadmap_changes = _update_roadmap_checkboxes(content, closed_feats)
        if roadmap_changes:
            changes.extend(roadmap_changes)

    # 3) Update date
    today = date.today().isoformat()
    new_content = re.sub(
        r"Last updated: \d{4}-\d{2}-\d{2}",
        f"Last updated: {today}",
        content,
    )
    if new_content != content:
        content = new_content

    # Write if changed
    if content != original:
        STATE_FILE.write_text(content, encoding="utf-8")
        cfg["last_sync"] = today
        save_config(cfg)
        print(green("PROJECT_STATE.md updated:"))
        for c in changes:
            print(f"  - {c}")
        print(f"  - Last updated: {today}")
    else:
        print("PROJECT_STATE.md already up to date.")


def _format_known_issues(bug_issues):
    if not bug_issues:
        return "\nNo open bug issues.\n"
    lines = ["\n"]
    for i, issue in enumerate(bug_issues, 1):
        lines.append(f"{i}. #{issue['number']}: {issue['title']}")
    lines.append("")
    return "\n".join(lines)


def _extract_section(content, heading):
    pattern = re.compile(
        r"## " + re.escape(heading) + r"\n(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1) if match else ""


def _replace_section(content, heading, new_body):
    pattern = re.compile(
        r"(## " + re.escape(heading) + r"\n)(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )
    match = pattern.search(content)
    if match:
        return content[:match.start(2)] + new_body + content[match.end(2):]
    return content


def _update_roadmap_checkboxes(content, closed_feats):
    """Update - [ ] lines in roadmap if matching closed feature issues."""
    changes = []
    closed_titles = [_normalize(f["title"]) for f in closed_feats]
    closed_words_list = [set(t.split()) for t in closed_titles]

    lines = content.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"\s*- \[ \]", line):
            line_norm = _normalize(line)
            line_words = set(line_norm.split())
            for j, feat_words in enumerate(closed_words_list):
                overlap = line_words & feat_words
                # Match if 3+ meaningful words overlap or substring match
                meaningful = {w for w in overlap if len(w) > 2}
                if len(meaningful) >= 3 or closed_titles[j] in line_norm:
                    lines[i] = line.replace("- [ ]", "- [x]", 1)
                    changes.append(
                        f"Checked: {line.strip()[:60]} "
                        f"(matched #{closed_feats[j]['number']})"
                    )
                    break
    return "\n".join(lines), changes


def _normalize(text):
    """Lowercase, strip markdown/punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"\[.*?\]", "", text)  # remove [BUG] [FEAT] etc
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def cmd_validate(args):
    print(bold("VALIDATE terrain40k"))
    ok_count = 0
    warn_count = 0
    fail_count = 0

    # 1) Version vs tag
    version = get_bl_info_version()
    tag = get_latest_tag()
    if version and tag:
        expected_tag = f"v{version}"
        if expected_tag == tag:
            print(f"  {green('[OK]')}   bl_info v{version} matches latest tag {tag}")
            ok_count += 1
        else:
            print(f"  {yellow('[WARN]')} bl_info v{version} != latest tag {tag}")
            warn_count += 1
    elif version:
        print(f"  {yellow('[WARN]')} bl_info v{version}, no git tags found")
        warn_count += 1
    else:
        print(f"  {red('[FAIL]')} Could not parse bl_info version")
        fail_count += 1

    # 2) Python compile check
    py_files = list(ADDON_DIR.rglob("*.py"))
    compile_errors = []
    for pf in py_files:
        try:
            py_compile.compile(str(pf), doraise=True)
        except py_compile.PyCompileError as e:
            compile_errors.append(str(e))
    if compile_errors:
        print(f"  {red('[FAIL]')} {len(compile_errors)} file(s) have syntax errors:")
        for err in compile_errors:
            print(f"         {err}")
        fail_count += 1
    else:
        print(f"  {green('[OK]')}   {len(py_files)} Python files compile without errors")
        ok_count += 1

    # 3) PROJECT_STATE freshness
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "update_project_state.py"),
         "--check-only"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(REPO_ROOT),
    )
    if result.returncode == 0:
        print(f"  {green('[OK]')}   PROJECT_STATE.md appears current")
        ok_count += 1
    else:
        print(f"  {yellow('[WARN]')} PROJECT_STATE.md may be outdated")
        warn_count += 1

    # 4) TODO/FIXME scan
    todos = []
    for pf in py_files:
        try:
            lines = pf.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for line_num, line in enumerate(lines, 1):
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
                rel = pf.relative_to(REPO_ROOT)
                todos.append(f"  {str(rel)}:{line_num}  {line.strip()}")
    if todos:
        print(f"  {yellow('[WARN]')} {len(todos)} TODO/FIXME found:")
        for t in todos[:10]:
            print(f"         {t}")
        if len(todos) > 10:
            print(f"         ... and {len(todos) - 10} more")
        warn_count += 1
    else:
        print(f"  {green('[OK]')}   No TODO/FIXME found")
        ok_count += 1

    # Summary
    print()
    print(f"Results: {green(f'{ok_count} OK')}, {yellow(f'{warn_count} WARN')}, {red(f'{fail_count} FAIL')}")
    sys.exit(1 if fail_count > 0 else 0)


def cmd_build(args):
    version = get_bl_info_version() or "unknown"
    if args.out:
        out_path = Path(args.out)
    else:
        out_path = REPO_ROOT / f"terrain40k-v{version}.zip"

    file_count = 0
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src in sorted(ADDON_DIR.rglob("*")):
            if src.is_dir():
                continue
            if "__pycache__" in src.parts or src.suffix == ".pyc":
                continue
            arcname = str(Path("terrain40k") / src.relative_to(ADDON_DIR))
            zf.write(src, arcname)
            file_count += 1

    size_kb = out_path.stat().st_size / 1024
    print(green(f"Built: {out_path}"))
    print(f"  {file_count} files, {size_kb:.1f} KB")


def cmd_milestone(args):
    cfg = get_config()
    repo = cfg["repo"]
    version = args.version
    if not version.startswith("v"):
        version = f"v{version}"

    # Check if milestone exists
    try:
        milestones = gh_run(["api", f"repos/{repo}/milestones"])
    except DevTrackerError:
        milestones = []

    existing = None
    for ms in milestones:
        if ms["title"] == version:
            existing = ms
            break

    if existing:
        opn = existing["open_issues"]
        closed = existing["closed_issues"]
        total = opn + closed
        pct = int(closed / total * 100) if total > 0 else 0
        print(bold(f"Milestone: {version}"))
        print(f"  Open:   {opn}")
        print(f"  Closed: {closed}")
        print(f"  Progress: {pct}%")
        print(f"  URL: {existing.get('html_url', 'N/A')}")
    else:
        result = gh_run([
            "api", f"repos/{repo}/milestones",
            "--method", "POST",
            "--field", f"title={version}",
        ])
        print(green(f"Created milestone: {version}"))
        if isinstance(result, dict) and "html_url" in result:
            print(f"  URL: {result['html_url']}")

    # Save as default
    cfg["default_milestone"] = version
    save_config(cfg)
    print(f"  Set as default milestone for new issues.")


# ── Argument parser ────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="devtracker",
        description="GitHub-centric dev tracker for terrain40k",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Project overview")

    pi = sub.add_parser("issues", help="List open GitHub issues")
    pi.add_argument("--label", choices=["bug", "enhancement", "task"])
    pi.add_argument("--limit", type=int, default=30)

    pa = sub.add_parser("add", help="Create a GitHub issue")
    pa.add_argument("type", choices=["bug", "feat", "task"])
    pa.add_argument("title")
    pa.add_argument("--body", default=None)
    pa.add_argument(
        "--no-milestone", action="store_true",
        help="Do not assign default milestone",
    )

    pc = sub.add_parser("close", help="Close a GitHub issue")
    pc.add_argument("number", type=int)
    pc.add_argument("--comment", default=None)

    sub.add_parser("sync", help="Sync GitHub issues -> PROJECT_STATE.md")

    sub.add_parser("validate", help="Validate addon health")

    pb = sub.add_parser("build", help="Build addon zip")
    pb.add_argument("--out", default=None, help="Output zip path")

    pm = sub.add_parser("milestone", help="Create or show a GitHub milestone")
    pm.add_argument("version", help="Version string, e.g. v0.2.0")

    return p


# ── Main ───────────────────────────────────────────────────────────────────

COMMANDS = {
    "status": cmd_status,
    "issues": cmd_issues,
    "add": cmd_add,
    "close": cmd_close,
    "sync": cmd_sync,
    "validate": cmd_validate,
    "build": cmd_build,
    "milestone": cmd_milestone,
}


def main():
    parser = build_parser()
    args = parser.parse_args()
    # Ensure config exists
    cfg = get_config()
    if not CONFIG_FILE.exists():
        save_config(cfg)
    try:
        COMMANDS[args.command](args)
    except DevTrackerError as e:
        fail(str(e))
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
