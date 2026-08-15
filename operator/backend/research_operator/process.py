"""Small process helpers with line-by-line worker logging."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Callable, Mapping, Sequence


class ProcessError(RuntimeError):
    pass


def run_streaming(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
) -> None:
    """Run a workload while preserving a concise, observable job log."""
    env = os.environ.copy()
    if environment:
        env.update({key: str(value) for key, value in environment.items()})
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        if on_line and line:
            on_line(line)
    return_code = process.wait()
    if return_code != 0:
        rendered = " ".join(command)
        raise ProcessError(f"command exited {return_code}: {rendered}")
