"""Host-agnostic git plumbing for the body loop.

State lives in git (data/ is the field and its records). Any host with a
clone and push rights can pull, run, and push back. Nothing here is
GitHub-specific.
"""
from __future__ import annotations

import subprocess
import time

from .paths import PACKAGE_ROOT


class GitError(RuntimeError):
    pass


def git(*args: str, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess:
    p = subprocess.run(["git", *args], cwd=PACKAGE_ROOT, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {p.stderr.strip()[:500]}")
    return p


def available() -> bool:
    try:
        return git("rev-parse", "--is-inside-work-tree", check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def commit(message: str, paths: list[str] | tuple[str, ...] = ("data/",)) -> bool:
    """Stage paths and commit if anything changed. Returns True when a commit was made."""
    paths = [p for p in paths if (PACKAGE_ROOT / p).exists()]
    if not paths:
        return False
    git("add", "--", *paths, check=False)
    if git("diff", "--staged", "--quiet", check=False).returncode == 0:
        return False
    git("commit", "-m", message)
    return True


def pull() -> bool:
    b = branch()
    p = git("pull", "--rebase", "origin", b, check=False, timeout=300)
    if p.returncode != 0:
        git("rebase", "--abort", check=False)
        return False
    return True


def sync(retries: int = 5) -> bool:
    """pull --rebase then push, with backoff. Returns True when pushed."""
    b = branch()
    for i in range(retries):
        if pull() and git("push", "origin", f"HEAD:{b}", check=False, timeout=300).returncode == 0:
            return True
        time.sleep(2 * (i + 1))
    return False


def find_commit(grep: str) -> str | None:
    out = git("log", f"--grep={grep}", "-1", "--format=%H", check=False).stdout.strip()
    return out or None


def revert(sha: str, message: str) -> bool:
    if git("revert", "--no-edit", sha, check=False).returncode != 0:
        git("revert", "--abort", check=False)
        return False
    git("commit", "--amend", "-m", message, check=False)
    return True
