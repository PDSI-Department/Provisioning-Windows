"""
PowerShell execution engine.

Runs PowerShell scripts and inline commands via subprocess,
captures output, enforces timeouts, returns structured results.

Security notes:
- Always uses -NoProfile -NonInteractive to avoid user-profile side effects.
- ExecutionPolicy Bypass is needed for unsigned scripts in provisioning context.
- No user input is interpolated unsafely — arguments are passed as PS parameters.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

POWERSHELL_EXE = "powershell.exe"

# Base flags for every PS invocation
BASE_FLAGS = [
    "-NoProfile",
    "-NonInteractive",
    "-ExecutionPolicy", "Bypass",
]


@dataclass
class PSResult:
    """Result of a PowerShell execution."""

    success: bool
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    timed_out: bool = False
    error_message: str = ""


class PowerShellRunner:
    """Runs PowerShell scripts and commands."""

    def __init__(self, working_dir: str | Path | None = None):
        self.working_dir = str(working_dir) if working_dir else None

    def run_script(
        self,
        script_path: str | Path,
        arguments: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> PSResult:
        """
        Run a .ps1 script file with named parameters.

        Args:
            script_path: Absolute or relative path to the .ps1 file.
            arguments: Named parameters passed as -Key Value pairs.
            timeout: Max execution time in seconds.
        """
        script_path = Path(script_path)
        if not script_path.exists():
            return PSResult(
                success=False,
                exit_code=-1,
                error_message=f"Script not found: {script_path}",
            )

        cmd = [POWERSHELL_EXE, *BASE_FLAGS, "-File", str(script_path)]

        # Append named parameters
        if arguments:
            for key, value in arguments.items():
                cmd.extend([f"-{key}", str(value)])

        logger.info("PS script: %s %s", script_path.name, arguments or "")
        return self._execute(cmd, timeout)

    def run_command(self, command: str, timeout: int = 300) -> PSResult:
        """
        Run an inline PowerShell command string.

        Args:
            command: The PowerShell command to execute.
            timeout: Max execution time in seconds.
        """
        cmd = [POWERSHELL_EXE, *BASE_FLAGS, "-Command", command]
        logger.info("PS command: %s", command[:120])
        return self._execute(cmd, timeout)

    def _execute(self, cmd: list[str], timeout: int) -> PSResult:
        """Execute a subprocess command and capture results."""
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            success = proc.returncode == 0

            result = PSResult(
                success=success,
                exit_code=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                duration_ms=duration_ms,
            )

            if not success:
                result.error_message = proc.stderr.strip() or f"Exit code {proc.returncode}"
                logger.warning("PS failed (exit %d): %s", proc.returncode, result.error_message[:200])
            else:
                logger.debug("PS success in %dms", duration_ms)

            return result

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error("PS timed out after %ds", timeout)
            return PSResult(
                success=False,
                exit_code=-1,
                duration_ms=duration_ms,
                timed_out=True,
                error_message=f"Timed out after {timeout}s",
            )
        except FileNotFoundError:
            return PSResult(
                success=False,
                exit_code=-1,
                error_message=f"PowerShell executable not found: {POWERSHELL_EXE}",
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception("PS execution error")
            return PSResult(
                success=False,
                exit_code=-1,
                duration_ms=duration_ms,
                error_message=str(exc),
            )
