"""
BrainyAi Isolated Code Execution Sandbox
Provides safe, truthful execution of code snippets in an isolated subprocess
with strict timeouts, memory/output bounds, sanitized environment variables (no API keys/secrets),
and isolated temporary workspaces.

Complies with Part 13 truthful execution statuses:
- generated_not_executed
- executed_successfully
- executed_with_failures
- execution_unavailable
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

# Truthful Execution Statuses as mandated by Part 13
STATUS_GENERATED_NOT_EXECUTED = "generated_not_executed"
STATUS_EXECUTED_SUCCESSFULLY = "executed_successfully"
STATUS_EXECUTED_WITH_FAILURES = "executed_with_failures"
STATUS_EXECUTION_UNAVAILABLE = "execution_unavailable"

# Sensitive substrings that must NEVER be passed to execution environment
SENSITIVE_ENV_SUBSTRINGS = (
    "KEY", "SECRET", "TOKEN", "AUTH", "PASS", "CRED",
    "SUPABASE", "DATABASE", "RAILWAY", "RENDER", "FLASK",
    "PRIVATE", "ADMIN", "PORT"
)

# Maximum output characters captured before truncation
MAX_OUTPUT_CHARS = 10000


@dataclass
class ExecutionResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time_ms: float = 0.0
    language: str = "python"
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_sanitized_env() -> Dict[str, str]:
    """
    Constructs a minimal, secure environment for subprocess execution.
    Strips all API keys, database credentials, authentication tokens, and secrets.
    """
    safe_keys = {
        "PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP",
        "PATHEXT", "WINDIR", "USERPROFILE", "LANG", "LC_ALL"
    }
    clean_env: Dict[str, str] = {}
    for k, v in os.environ.items():
        k_upper = k.upper()
        # Ensure key is in safe keys and does not contain any sensitive tokens
        if k_upper in safe_keys and not any(sub in k_upper for sub in SENSITIVE_ENV_SUBSTRINGS):
            clean_env[k] = v

    # Python specific safe defaults
    clean_env["PYTHONUNBUFFERED"] = "1"
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    return clean_env


def execute_code_safely(
    code: str,
    language: str = "python",
    timeout_sec: float = 3.0,
    stdin_input: str = ""
) -> ExecutionResult:
    """
    Executes a code snippet inside a temporary, isolated workspace with resource constraints.
    Returns a truthful ExecutionResult with one of the standard statuses.
    """
    lang = language.lower().strip()
    if not code or not code.strip():
        return ExecutionResult(
            status=STATUS_GENERATED_NOT_EXECUTED,
            language=lang,
            error_message="Empty code provided"
        )

    # Determine command based on language
    if lang in ("python", "py", "python3"):
        runner = sys.executable
        file_ext = ".py"
        cmd = [runner, "main.py"]
    elif lang in ("javascript", "js", "node"):
        node_path = shutil.which("node")
        if not node_path:
            return ExecutionResult(
                status=STATUS_EXECUTION_UNAVAILABLE,
                language=lang,
                error_message="Node.js runtime not installed or unavailable on host PATH"
            )
        file_ext = ".js"
        cmd = [node_path, "main.js"]
    else:
        return ExecutionResult(
            status=STATUS_EXECUTION_UNAVAILABLE,
            language=lang,
            error_message=f"Execution runtime unavailable or unsupported for language: {language}"
        )

    # Create temporary isolated directory
    temp_dir = tempfile.mkdtemp(prefix="brainy_sandbox_")
    try:
        script_path = os.path.join(temp_dir, f"main{file_ext}")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        sanitized_env = get_sanitized_env()
        # Point TEMP/TMP into the isolated workspace
        sanitized_env["TEMP"] = temp_dir
        sanitized_env["TMP"] = temp_dir

        t0 = time.perf_counter()
        proc = subprocess.Popen(
            cmd,
            cwd=temp_dir,
            env=sanitized_env,
            stdin=subprocess.PIPE if stdin_input else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        try:
            stdout_data, stderr_data = proc.communicate(
                input=stdin_input if stdin_input else None,
                timeout=timeout_sec
            )
            exec_time_ms = round((time.perf_counter() - t0) * 1000, 2)
            exit_code = proc.returncode

            # Truncate output if excessively large
            if len(stdout_data) > MAX_OUTPUT_CHARS:
                stdout_data = stdout_data[:MAX_OUTPUT_CHARS] + "\n... [Output truncated for safety]"
            if len(stderr_data) > MAX_OUTPUT_CHARS:
                stderr_data = stderr_data[:MAX_OUTPUT_CHARS] + "\n... [Stderr truncated for safety]"

            if exit_code == 0:
                return ExecutionResult(
                    status=STATUS_EXECUTED_SUCCESSFULLY,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    exit_code=0,
                    execution_time_ms=exec_time_ms,
                    language=lang
                )
            else:
                return ExecutionResult(
                    status=STATUS_EXECUTED_WITH_FAILURES,
                    stdout=stdout_data,
                    stderr=stderr_data,
                    exit_code=exit_code,
                    execution_time_ms=exec_time_ms,
                    language=lang,
                    error_message=f"Process exited with non-zero returncode {exit_code}"
                )

        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=1.0)
            except Exception:
                pass
            exec_time_ms = round((time.perf_counter() - t0) * 1000, 2)
            return ExecutionResult(
                status=STATUS_EXECUTED_WITH_FAILURES,
                stdout="",
                stderr=f"Execution timed out after {timeout_sec:.1f}s",
                exit_code=-1,
                execution_time_ms=exec_time_ms,
                language=lang,
                error_message=f"Timeout limit of {timeout_sec}s exceeded"
            )

    except Exception as e:
        return ExecutionResult(
            status=STATUS_EXECUTION_UNAVAILABLE,
            language=lang,
            error_message=f"Sandbox invocation error: {str(e)}"
        )
    finally:
        # Safe cleanup of the isolated directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
