#!/usr/bin/env python3
"""
Update PROJECT_STATE.md with current info from the codebase.

Usage:
    python tools/update_project_state.py              # Update in place
    python tools/update_project_state.py --check-only # Exit 1 if outdated
"""

import ast
import os
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = REPO_ROOT / "addon" / "terrain40k"
STATE_FILE = REPO_ROOT / "docs" / "PROJECT_STATE.md"
CHANGELOG_FILE = REPO_ROOT / "CHANGELOG.md"


def get_bl_info_version():
    """Extract version tuple from bl_info in __init__.py."""
    init_path = ADDON_DIR / "__init__.py"
    if not init_path.exists():
        return None
    with open(init_path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "bl_info":
                    if isinstance(node.value, ast.Dict):
                        for key, val in zip(node.value.keys, node.value.values):
                            if (isinstance(key, ast.Constant)
                                    and key.value == "version"
                                    and isinstance(val, ast.Tuple)):
                                return ".".join(
                                    str(e.value) for e in val.elts
                                )
    return None


def scan_generators():
    """Scan generator directory for implemented module files."""
    gen_dir = ADDON_DIR / "generator"
    modules = []
    if not gen_dir.exists():
        return modules
    for py_file in sorted(gen_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        name = py_file.stem
        # Check if it has a generate_ function
        with open(py_file) as f:
            content = f.read()
        if re.search(r"def generate_", content):
            modules.append(name)
    return modules


def scan_features():
    """Scan codebase for feature markers."""
    features = {}
    for py_file in ADDON_DIR.rglob("*.py"):
        with open(py_file) as f:
            try:
                content = f.read()
            except Exception:
                continue
        # Check for key features
        if "def cleanup_mesh" in content:
            features["cleanup_mesh"] = True
        if "def boolean_difference" in content:
            features["boolean_ops"] = True
        if "def add_connectors" in content:
            features["connectors"] = True
        if "def apply_damage" in content:
            features["damage"] = True
        if "def split_for_print" in content:
            features["auto_split"] = True
        if "gothic_arch" in content.lower():
            features["gothic_arch"] = True
        if "def create_buttress" in content:
            features["buttress"] = True
        if "def create_pillar" in content:
            features["pillar_primitive"] = True
    return features


def get_last_changelog_entries(count=3):
    """Extract last N version entries from CHANGELOG.md."""
    if not CHANGELOG_FILE.exists():
        return ""
    with open(CHANGELOG_FILE) as f:
        content = f.read()
    # Split by version headers
    sections = re.split(r"\n(?=## )", content)
    entries = [s.strip() for s in sections if s.strip().startswith("## [")]
    return "\n\n".join(entries[:count])


def update_state_header(content, version):
    """Update the version and date in the state file header."""
    today = date.today().isoformat()
    content = re.sub(
        r"Last updated: \d{4}-\d{2}-\d{2}",
        f"Last updated: {today}",
        content,
    )
    if version:
        content = re.sub(
            r"Version: [\d.]+",
            f"Version: {version}",
            content,
        )
        content = re.sub(
            r"`[\d.]+` — ",
            f"`{version}` — ",
            content,
        )
    return content


def main():
    check_only = "--check-only" in sys.argv

    if not STATE_FILE.exists():
        print(f"PROJECT_STATE.md not found at {STATE_FILE}")
        sys.exit(1)

    with open(STATE_FILE) as f:
        current_content = f.read()

    version = get_bl_info_version()
    generators = scan_generators()
    features = scan_features()

    print(f"Version from bl_info: {version}")
    print(f"Generator modules found: {generators}")
    print(f"Features detected: {list(features.keys())}")

    # Build updated content
    updated = update_state_header(current_content, version)

    if check_only:
        if updated != current_content:
            print("PROJECT_STATE.md is outdated (header mismatch).")
            sys.exit(1)
        print("PROJECT_STATE.md appears current.")
        sys.exit(0)

    with open(STATE_FILE, "w") as f:
        f.write(updated)
    print(f"Updated {STATE_FILE}")


if __name__ == "__main__":
    main()
