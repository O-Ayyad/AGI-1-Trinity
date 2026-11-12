from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_READ_BYTES = 200_000
MAX_OUTPUT_CHARS = 20_000
DEFAULT_TIMEOUT = 30


class ToolError(Exception):
    """A tool call that was rejected or failed. The message is shown to the model."""


@dataclass(frozen=True)
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    def __str__(self) -> str:
        status = "timed out" if self.timed_out else f"exit code {self.returncode}"
        return f"[{status}]\n--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated {len(text) - MAX_OUTPUT_CHARS} chars]"


class ToolLayer:
    #only allow files in workdir to be manipulated. Reject all other files.

    def __init__(self, workdir: str | os.PathLike) -> None:
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        if not path or "\0" in path:
            raise ToolError("A non-empty path is required.")
        # resolve() follows symlinks so a link pointing outside the workdir is caught too
        target = (self.workdir / path).resolve()
        if not target.is_relative_to(self.workdir):
            raise ToolError(f"Path {path!r} is outside the working directory.")
        return target

    def _relative(self, target: Path) -> str:
        return str(target.relative_to(self.workdir))

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolError(f"{path!r} does not exist or is not a file.")
        if target.stat().st_size > MAX_READ_BYTES:
            raise ToolError(f"{path!r} is larger than {MAX_READ_BYTES} bytes.")
        return target.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        if target.is_dir():
            raise ToolError(f"{path!r} is a directory.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {self._relative(target)}."

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        """Replace exactly one occurrence of `old_text`."""
        content = self.read_file(path)
        count = content.count(old_text) if old_text else 0
        if count == 0:
            raise ToolError(f"old_text was not found in {path!r}.")
        if count > 1:
            raise ToolError(f"old_text occurs {count} times in {path!r}; include more context.")
        self.write_file(path, content.replace(old_text, new_text, 1))
        return f"Edited {path}."

    def execute_code(self, code: str, timeout: int = DEFAULT_TIMEOUT) -> ExecutionResult:
        """Run Python source with the working directory as cwd and a minimal environment."""
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.workdir), "PYTHONIOENCODING": "utf-8"}
        try:
            completed = subprocess.run(
                # -I isolated mode ignores python env vars and the user site dir
                [sys.executable, "-I", "-c", code],
                cwd=self.workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ExecutionResult(
                returncode=-1,
                stdout=_truncate(_as_text(exc.stdout)),
                stderr=_truncate(_as_text(exc.stderr)),
                timed_out=True,
            )
        return ExecutionResult(completed.returncode, _truncate(completed.stdout), _truncate(completed.stderr))

    def snapshot(self) -> dict[str, int]:
        #relative path -> mtime_ns for every file"""
        return {
            self._relative(p): p.stat().st_mtime_ns
            for p in self.workdir.rglob("*")
            if p.is_file() and not p.is_symlink()
        }

    def dispatch(self, name: str, tool_input: dict) -> str:
        #run a tool by name with model supplied input
        try:
            if name == "read_file":
                return self.read_file(tool_input["path"])
            if name == "write_file":
                return self.write_file(tool_input["path"], tool_input["content"])
            if name == "edit_file":
                return self.edit_file(tool_input["path"], tool_input["old_text"], tool_input["new_text"])
            if name == "execute_code":
                timeout = min(int(tool_input.get("timeout", DEFAULT_TIMEOUT)), 120)
                return str(self.execute_code(tool_input["code"], timeout))
        except KeyError as exc:
            raise ToolError(f"Missing required argument {exc.args[0]!r} for {name}.") from exc
        except OSError as exc:
            raise ToolError(f"{name} failed: {exc}") from exc
        raise ToolError(f"Unknown tool {name!r}.")


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read a UTF-8 text file from the working directory. Paths are relative to it.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path."}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file in the working directory. Parent folders are created.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "content": {"type": "string", "description": "Full file contents."},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edit_file",
        "description": "Replace one exact, unique occurrence of old_text with new_text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path."},
                "old_text": {"type": "string", "description": "Exact text to replace; must occur once."},
                "new_text": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "execute_code",
        "description": (
            "Run Python source code with the working directory as cwd. Returns the exit code, "
            "stdout and stderr. Use it to run files you wrote, e.g. "
            "`import runpy; runpy.run_path('main.py', run_name='__main__')`."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source to run."},
                "timeout": {"type": "integer", "description": "Seconds before the run is stopped (max 120)."},
            },
            "required": ["code"],
            "additionalProperties": False,
        },
    },
]
