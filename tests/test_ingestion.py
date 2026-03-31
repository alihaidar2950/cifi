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


def test_ingest_local_detects_test_output(tmp_path):
    logs = "FAILED tests/test_x.py::test_y - AssertionError"
    ctx = ingest_local(workspace=str(tmp_path), step_logs=logs)
    assert ctx.test_output is not None
