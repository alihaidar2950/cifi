"""Tests for CIFI ingestion."""

from cifi.ingestion import _extract_file_paths, ingest_local


def test_extract_file_paths_from_traceback():
    logs = """Traceback (most recent call last):
  File "src/api/handlers.py", line 42, in create_user
    validate(email)
  File "src/utils/validators.py", line 10, in validate
    raise ValueError("invalid")
"""
    paths = _extract_file_paths(logs)
    assert "src/api/handlers.py" in paths
    assert "src/utils/validators.py" in paths


def test_extract_file_paths_from_compiler_errors():
    logs = "src/main.ts:15:3 error TS2304: Cannot find name 'foo'."
    paths = _extract_file_paths(logs)
    assert "src/main.ts" in paths


def test_ingest_local_reads_workspace(tmp_path):
    # Create a minimal workspace
    (tmp_path / "requirements.txt").write_text("flask==3.0\n")
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def main(): pass\n")

    logs = 'File "src/app.py", line 1\n  SyntaxError: invalid syntax'
    ctx = ingest_local(
        workspace=str(tmp_path),
        step_logs=logs,
        repo="test/repo",
        branch="main",
        commit_sha="abc123",
    )
    assert ctx.repo == "test/repo"
    assert "src/app.py" in ctx.source_files
    assert "requirements.txt" in ctx.dependency_files
    assert ctx.failed_step_logs == logs


def test_ingest_local_stores_failed_step_logs(tmp_path):
    logs = "FAILED tests/test_x.py::test_y - AssertionError"
    ctx = ingest_local(workspace=str(tmp_path), step_logs=logs)
    assert ctx.failed_step_logs == logs


def test_ingest_local_blocks_path_traversal(tmp_path):
    """Files outside workspace referenced via .. must not be read."""
    # Place a sentinel file one level above the workspace
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("credentials")

    logs = f'File "../../{secret.name}"'
    ctx = ingest_local(workspace=str(tmp_path), step_logs=logs)
    assert not ctx.source_files  # traversal attempt must be silently dropped


def test_ingest_local_package_lock_not_collected(tmp_path):
    """package-lock.json should not be ingested (noisy truncated lockfile)."""
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 3}')
    ctx = ingest_local(workspace=str(tmp_path), step_logs="")
    assert "package-lock.json" not in ctx.dependency_files
