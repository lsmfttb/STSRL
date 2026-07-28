"""Strict Git checkout verification shared by retained T068 evidence scripts."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


def verify_exact_git_checkout(repo_root: Path, code_commit: str) -> None:
    """Require an exact HEAD and no tracked changes, including WSL gitfiles."""

    actual = git_output(repo_root, "rev-parse", "HEAD")
    if actual != code_commit:
        raise ValueError("source checkout HEAD does not match the exact code commit")
    status = git_output(repo_root, "status", "--porcelain", "--untracked-files=no")
    if status is None or status:
        raise ValueError("source checkout has tracked or staged changes")


def git_output(repo_root: Path, *arguments: str) -> str | None:
    """Run Git directly, then retry a Windows worktree gitfile through WSL."""

    safe_directory = f"safe.directory={repo_root}"
    commands = [
        [
            "git",
            "-c",
            safe_directory,
            "-C",
            str(repo_root),
            "-c",
            "core.autocrlf=true",
            *arguments,
        ]
    ]
    dot_git = repo_root / ".git"
    if dot_git.is_file():
        marker = dot_git.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            git_dir = marker.removeprefix("gitdir:").strip()
            match = re.fullmatch(r"([A-Za-z]):[/\\](.*)", git_dir)
            if match is not None:
                git_dir = f"/mnt/{match.group(1).lower()}/{match.group(2).replace(chr(92), '/')}"
            commands.append(
                [
                    "git",
                    "-c",
                    safe_directory,
                    "--git-dir",
                    git_dir,
                    "--work-tree",
                    str(repo_root),
                    "-c",
                    "core.autocrlf=true",
                    *arguments,
                ]
            )
    for command in commands:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    return None
