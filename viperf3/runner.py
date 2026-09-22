"""Async runner that spawns iperf3 and streams parsed events."""
from __future__ import annotations

import asyncio
import os
import shutil
from typing import AsyncIterator, Optional

from .config import ClientConfig
from .parser import ErrorEvent, ParsedEvent, parse_line


def find_iperf3() -> Optional[str]:
    """Locate the iperf3 executable, preferring the locally built one."""
    local = "/usr/local/bin/iperf3"
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which("iperf3")


class IperfRunner:
    """Runs an iperf3 client and yields parsed events as they arrive."""

    def __init__(self, config: ClientConfig, executable: Optional[str] = None):
        self.config = config
        self.executable = executable or find_iperf3()
        self._process: Optional[asyncio.subprocess.Process] = None
        self._stderr: list[str] = []
        self._stopped = False  # set when the user requested termination

    @property
    def command(self) -> list[str]:
        return [self.executable or "iperf3", *self.config.to_args()]

    async def run(self) -> AsyncIterator[ParsedEvent]:
        if not self.executable:
            yield ErrorEvent("iperf3 executable not found in PATH")
            return

        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert self._process.stdout is not None

        saw_error = False
        try:
            async for raw in self._process.stdout:
                line = raw.decode("utf-8", errors="replace")
                event = parse_line(line)
                if event is not None:
                    saw_error = saw_error or isinstance(event, ErrorEvent)
                    yield event
        finally:
            await self._drain_stderr()
            code = await self._process.wait()
            # Only surface an exit-code error if the stream didn't already
            # report one and the user didn't stop the test themselves.
            if code not in (0, None) and not saw_error and not self._stopped:
                msg = "".join(self._stderr).strip() or f"iperf3 exited with code {code}"
                yield ErrorEvent(msg)

    async def _drain_stderr(self) -> None:
        if self._process and self._process.stderr:
            data = await self._process.stderr.read()
            if data:
                self._stderr.append(data.decode("utf-8", errors="replace"))

    def stop(self) -> None:
        self._stopped = True
        if self._process and self._process.returncode is None:
            try:
                self._process.terminate()
            except ProcessLookupError:
                pass
