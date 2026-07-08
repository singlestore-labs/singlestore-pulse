#!/usr/bin/env python3
"""Release script for singlestore-pulse.

Usage (called from the Makefile):
    python scripts/python-release.py <version_file> [--version X.Y.Z]

Interactive (prompts for version):
    python scripts/python-release.py src/pulse_otel/version.py

Non-interactive (for CI/agents):
    python scripts/python-release.py src/pulse_otel/version.py --version 0.4.15

Flow:
1. Validates on master, clean tree, up-to-date with origin.
2. Reads current version from the version file.
3. Prompts for patch/minor/major/custom (or uses --version).
4. Validates monotonicity against remote tags (vX.Y.Z).
5. Bumps __version__ in the version file.
6. Creates a release branch, commits, pushes, opens a PR.
7. On PR merge, python-release.yml auto-tags vX.Y.Z.
"""

import argparse
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

BRANCH = "master"


def run_command(args: Iterable[str], capture_output: bool = True) -> tuple[bool, str]:
    args_list: list[str] = list(args)
    try:
        result = subprocess.run(args_list, capture_output=capture_output, text=True, check=True)
        return True, (result.stdout.strip() if capture_output else "")
    except subprocess.CalledProcessError as e:
        output = (e.stderr or e.stdout or str(e)).strip()
        return False, output


def get_current_version(version_file: Path) -> str:
    if not version_file.exists():
        print(f"❌ {version_file} not found!")
        sys.exit(1)
    content = version_file.read_text()
    match = re.search(r'__version__ = ["\']([^"\']+)["\']', content)
    if not match:
        print(f"❌ Could not parse __version__ from {version_file}")
        sys.exit(1)
    return match.group(1)


def parse_version(version: str) -> tuple:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        print(f"❌ Invalid version format: {version}")
        sys.exit(1)
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def get_latest_tag() -> str:
    ok, output = run_command(["git", "ls-remote", "--tags", "--refs", "origin"])
    if not ok:
        print("⚠️  Could not retrieve remote tags.")
        return "None"
    latest_tuple = None
    latest_str = "None"
    for line in output.splitlines():
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        _, ref = parts
        if not ref.startswith("refs/tags/v"):
            continue
        tag_version = ref.split("refs/tags/v", 1)[1]
        # Skip legacy non-semver tags (e.g. v0.4) silently rather than aborting.
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", tag_version)
        if not m:
            continue
        vt = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if latest_tuple is None or vt > latest_tuple:
            latest_tuple = vt
            latest_str = tag_version
    if latest_tuple is None:
        print("ℹ️  No existing vX.Y.Z tags found on remote")  # noqa: RUF001
    return latest_str


def update_version_file(version_file: Path, new_version: str) -> None:
    content = version_file.read_text()
    updated = re.sub(r'__version__ = ["\'][^"\']+["\']', f'__version__ = "{new_version}"', content)
    version_file.write_text(updated)
    print(f"✅ Updated {version_file} to {new_version}")


def prompt_version(major: int, minor: int, patch: int) -> str:
    print("\nSelect the next version:")
    print(f"  1) patch   v{major}.{minor}.{patch + 1}")
    print(f"  2) minor   v{major}.{minor + 1}.0")
    print(f"  3) major   v{major + 1}.0.0")
    print("  4) custom")
    choice = input("\nChoice [1-4]: ").strip()
    if choice == "1":
        return f"{major}.{minor}.{patch + 1}"
    elif choice == "2":
        return f"{major}.{minor + 1}.0"
    elif choice == "3":
        return f"{major + 1}.0.0"
    elif choice == "4":
        v = input("Enter version (X.Y.Z): ").strip().lstrip("v")
        parse_version(v)
        return v
    else:
        print("❌ Invalid choice")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Release singlestore-pulse")
    parser.add_argument("version_file", help="Path to the version file (e.g. src/pulse_otel/version.py)")
    parser.add_argument(
        "--version", dest="target_version", help="Version to release (X.Y.Z). Skips interactive prompts."
    )
    args = parser.parse_args()

    version_file = Path(args.version_file)
    interactive = args.target_version is None

    # Preflight
    ok, _ = run_command(["gh", "--version"])
    if not ok:
        print("❌ GitHub CLI (gh) not installed")
        sys.exit(1)
    ok, _ = run_command(["gh", "auth", "status"])
    if not ok:
        print("❌ gh not authenticated")
        sys.exit(1)

    ok, branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if not ok or branch != BRANCH:
        print(f"❌ Must be on {BRANCH} branch")
        sys.exit(1)
    ok, _ = run_command(["git", "diff", "--quiet"])
    ok2, _ = run_command(["git", "diff", "--cached", "--quiet"])
    if not ok or not ok2:
        print("❌ Working tree dirty; commit or stash first")
        sys.exit(1)

    ok, out = run_command(["git", "fetch", "--quiet", "origin", BRANCH])
    if not ok:
        print(f"❌ git fetch origin {BRANCH} failed: {out}")
        sys.exit(1)
    ok, _ = run_command(["git", "merge-base", "--is-ancestor", f"origin/{BRANCH}", "HEAD"])
    if not ok:
        print(f"❌ Local {BRANCH} behind origin; pull first")
        sys.exit(1)
    _, local_sha = run_command(["git", "rev-parse", "HEAD"])
    _, remote_sha = run_command(["git", "rev-parse", f"origin/{BRANCH}"])
    if local_sha != remote_sha:
        print(f"❌ Local {BRANCH} has unpushed commits (push first)")
        sys.exit(1)

    # Version
    current = get_current_version(version_file)
    major, minor, patch = parse_version(current)
    latest_tag = get_latest_tag()
    print(f"\nCurrent version: v{current}")
    if latest_tag != "None":
        print(f"Latest tag: v{latest_tag}")

    if interactive:
        new_version = prompt_version(major, minor, patch)
    else:
        new_version = args.target_version.lstrip("v")
        parse_version(new_version)
        print(f"Target version: v{new_version}")

    # Validate monotonicity
    if latest_tag != "None" and parse_version(new_version) <= parse_version(latest_tag):
        print(f"❌ v{new_version} is not greater than latest tag v{latest_tag}")
        sys.exit(1)

    if interactive:
        confirm = input(f"\nRelease v{new_version}? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    # Create release
    release_branch = f"release-v{new_version}"
    ok, out = run_command(["git", "checkout", "-b", release_branch])
    if not ok:
        print(f"❌ Failed to create branch: {out}")
        sys.exit(1)

    update_version_file(version_file, new_version)
    run_command(["git", "add", str(version_file)])

    commit_msg = f"Release v{new_version}"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(commit_msg)
        msg_file = f.name
    ok, out = run_command(["git", "commit", "-F", msg_file])
    if not ok:
        print(f"❌ Failed to commit: {out}")
        sys.exit(1)
    ok, out = run_command(["git", "push", "-u", "origin", release_branch])
    if not ok:
        print(f"❌ Failed to push: {out}")
        sys.exit(1)

    pr_title = f"Release v{new_version}"
    pr_body = (
        f"Releasing `singlestore-pulse` v{new_version}.\n\n"
        f"On merge, `python-release.yml` tags `v{new_version}` and creates a GitHub release."
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(pr_body)
        body_file = f.name

    ok, pr_url = run_command(
        [
            "gh",
            "pr",
            "create",
            "--base",
            BRANCH,
            "--head",
            release_branch,
            "--title",
            pr_title,
            "--body-file",
            body_file,
        ]
    )
    if ok:
        print(f"\n✅ Release PR opened: {pr_url}")
        print("   Review + merge; CI auto-tags on merge.")
    else:
        print(f"❌ Failed to create PR: {pr_url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
