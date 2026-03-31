"""Integration tests — call real GitHub Models API.

These tests require a valid GITHUB_TOKEN env var with access to GitHub Models.
Run with: make test-integration
Skip with: make test  (only runs unit tests)
"""

import os

import pytest

from cifi.analyzer import analyze
from cifi.config import Config
from cifi.preprocessor import preprocess
from cifi.schemas import AnalysisResult, FailureContext

# Skip entire module if no token available
pytestmark = pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"), reason="GITHUB_TOKEN not set")

# -- Realistic CI failure logs --

PYTEST_FAILURE_LOG = """\
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.0.0, pluggy-1.5.0
rootdir: /home/runner/work/myapp/myapp
collected 24 items

tests/test_users.py::test_list_users PASSED
tests/test_users.py::test_create_user FAILED
tests/test_users.py::test_delete_user PASSED
tests/test_auth.py::test_login PASSED
tests/test_auth.py::test_signup PASSED

=================================== FAILURES ===================================
__________________________ test_create_user ___________________________________

    def test_create_user():
        user = create_user(name="alice", email="alice@example")
>       assert user.is_valid()
E       AssertionError: assert False
E        +  where False = <User name='alice' email='alice@example'>.is_valid()

tests/test_users.py:15: AssertionError
=========================== short test summary info ============================
FAILED tests/test_users.py::test_create_user - AssertionError: assert False
========================= 1 failed, 4 passed in 0.42s =========================
"""

BUILD_ERROR_LOG = """\
Step 1/8 : FROM python:3.12-slim
 ---> abc123def456
Step 4/8 : RUN pip install -r requirements.txt
 ---> Running in container_xyz
Collecting flask==3.0.0
  Downloading Flask-3.0.0.tar.gz (674 kB)
ERROR: Could not find a version that satisfies the requirement nonexistent-package==1.0.0
ERROR: No matching distribution found for nonexistent-package==1.0.0
The command '/bin/sh -c pip install -r requirements.txt' returned a non-zero code: 1
"""

TYPESCRIPT_ERROR_LOG = """\
> tsc --noEmit

src/components/UserForm.tsx:42:5 - error TS2322: \
Type 'string' is not assignable to type 'number'.

42     const age: number = formData.age;
       ~~~

src/components/UserForm.tsx:58:12 - error TS2345: \
Argument of type 'string' is not assignable to parameter of type 'User'.

58     saveUser(formData.name);
              ~~~~~~~~~~~~~~

Found 2 errors in the same file.
"""


@pytest.fixture
def config():
    return Config(
        llm_provider="github-models",
        llm_api_key=os.environ["GITHUB_TOKEN"],
        max_retries=2,
    )


async def test_analyze_pytest_failure(config):
    """Real LLM analysis of a pytest failure log."""
    context = FailureContext(
        run_id=100,
        repo="testowner/myapp",
        branch="feature/user-validation",
        commit_sha="abc1234",
        failed_step_logs=PYTEST_FAILURE_LOG,
        test_output=PYTEST_FAILURE_LOG,
    )
    processed = preprocess(context)
    result = await analyze(processed, config)

    assert isinstance(result, AnalysisResult)
    assert result.failure_type == "test_failure"
    assert result.confidence in ("high", "medium", "low")
    assert len(result.root_cause) > 10
    assert len(result.suggested_fix) > 10
    assert len(result.relevant_log_lines) > 0


async def test_analyze_build_error(config):
    """Real LLM analysis of a Docker build failure."""
    context = FailureContext(
        run_id=101,
        repo="testowner/myapp",
        branch="main",
        commit_sha="def5678",
        failed_step_logs=BUILD_ERROR_LOG,
        dependency_files={"requirements.txt": "flask==3.0.0\nnonexistent-package==1.0.0\n"},
    )
    processed = preprocess(context)
    result = await analyze(processed, config)

    assert isinstance(result, AnalysisResult)
    assert result.failure_type in ("build_error", "config_error")
    assert result.confidence in ("high", "medium", "low")
    assert "nonexistent" in result.root_cause.lower() or "package" in result.root_cause.lower()
    assert len(result.suggested_fix) > 10


async def test_analyze_typescript_error(config):
    """Real LLM analysis of TypeScript compilation errors."""
    context = FailureContext(
        run_id=102,
        repo="testowner/frontend",
        branch="refactor/forms",
        commit_sha="ghi9012",
        failed_step_logs=TYPESCRIPT_ERROR_LOG,
        source_files={
            "src/components/UserForm.tsx": (
                "interface User { name: string; age: number; }\n"
                "function saveUser(user: User) { /* ... */ }\n"
                "const formData = { name: 'Alice', age: '25' };\n"
                "const age: number = formData.age;\n"
                "saveUser(formData.name);\n"
            )
        },
    )
    processed = preprocess(context)
    result = await analyze(processed, config)

    assert isinstance(result, AnalysisResult)
    assert result.failure_type in ("build_error", "test_failure")
    assert result.confidence in ("high", "medium", "low")
    assert "type" in result.root_cause.lower() or "string" in result.root_cause.lower()
    assert len(result.relevant_log_lines) > 0
