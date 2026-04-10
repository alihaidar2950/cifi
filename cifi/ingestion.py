"""Log ingestion — read CI logs and source code from the local filesystem."""

import re
import subprocess
from pathlib import Path

from cifi.schemas import FailureContext

# Files to read as dependency manifests
_DEPENDENCY_FILES = [
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile",
]

# Max bytes to read per source file
_MAX_FILE_SIZE = 50_000


def _read_file_safe(path: Path, max_bytes: int = _MAX_FILE_SIZE) -> str | None:
    """Read a file, returning None if it doesn't exist or isn't text."""
    try:
        content = path.read_text(errors="replace")
        return content[:max_bytes]
    except (OSError, UnicodeDecodeError):
        return None


def _extract_file_paths(logs: str) -> list[str]:
    """Extract file paths mentioned in error logs."""
    # Match patterns like: path/to/file.py:42: or File "path/to/file.py"
    patterns = [
        re.compile(r'File "([^"]+)"'),
        re.compile(r"(\S+\.\w{1,5}):(\d+)"),
        re.compile(r"in\s+(\S+\.\w{1,5})"),
    ]
    paths: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(logs):
            paths.append(match.group(1))
    return list(dict.fromkeys(paths))  # dedupe, preserve order


def _git_diff(workspace: Path) -> str:
    """Get git diff of the most recent commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout[:_MAX_FILE_SIZE] if result.returncode == 0 else ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def ingest_local(
    workspace: str,
    step_logs: str,
    *,
    run_id: int = 0,
    repo: str = "",
    branch: str = "",
    commit_sha: str = "",
    pr_title: str | None = None,
    pr_description: str | None = None,
) -> FailureContext:
    """Tier 1: Read failure context from the local filesystem."""
    ws = Path(workspace)

    # Read source files mentioned in error logs
    source_files: dict[str, str] = {}
    for file_path in _extract_file_paths(step_logs):
        full_path = ws / file_path
        if full_path.is_file():
            content = _read_file_safe(full_path)
            if content:
                source_files[file_path] = content

    # Read dependency files from workspace root
    dependency_files: dict[str, str] = {}
    for dep_file in _DEPENDENCY_FILES:
        full_path = ws / dep_file
        content = _read_file_safe(full_path)
        if content:
            dependency_files[dep_file] = content

    # Git diff
    git_diff = _git_diff(ws)

    return FailureContext(
        run_id=run_id,
        repo=repo,
        branch=branch,
        commit_sha=commit_sha,
        failed_step_logs=step_logs,
        source_files=source_files,
        git_diff=git_diff,
        dependency_files=dependency_files,
        pr_title=pr_title,
        pr_description=pr_description,
    )
