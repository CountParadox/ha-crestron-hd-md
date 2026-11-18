"""Client for Crestron HD-MD series HDMI switchers (built-in web interface).

The switcher's web page talks to two things on plain HTTP:

    GET /                               the page itself, which embeds model,
                                        serial number, firmware and MAC
    GET /aj.html?a=rout|input|outp      JSON status
    GET /aj.html?a=command&cmd=..&p1=.. commands

Routing uses one command letter per output ("A" for output 1, "B" for output
2, ...) with the input number as p1; input 0 disconnects the output.

The web page's login only hides its own menus: the switcher answers status
requests and accepts commands whether or not anybody is logged in. This client
therefore needs no user name or password, and never logs in.

This module only depends on aiohttp so it can be tested without Home Assistant.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_PAGE_FIELDS = {
    "model": "model",
    "seriv": "serial",
    "firmv": "firmware",
    "mac": "mac",
    "host": "hostname",
}


class CrestronHdMdError(Exception):
    """Base error."""


class CrestronHdMdConnectionError(CrestronHdMdError):
    """The switcher could not be reached."""


def output_command(output: int) -> str:
    """Command letter for an output (1 -> 'A', 2 -> 'B')."""
    return chr(ord("A") + output - 1)


class CrestronHdMdClient:
    """Talk to one switcher."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        timeout: float = 6.0,
    ) -> None:
        self._session = session
        self.host = host
        self._timeout = timeout
        self._lock = asyncio.Lock()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> str:
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.get(
                    f"http://{self.host}/{path}", params=params
                ) as response:
                    if response.status >= 400:
                        raise CrestronHdMdError(f"HTTP {response.status} for {path}")
                    return await response.text(errors="replace")
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CrestronHdMdConnectionError(
                f"Cannot reach switcher at {self.host}: {err or type(err).__name__}"
            ) from err

    async def _json(self, params: dict[str, Any]) -> dict[str, Any]:
        text = (await self._get("aj.html", params)).strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except ValueError as err:
            raise CrestronHdMdError(
                f"Unexpected answer from {self.host}: {text[:80]!r}"
            ) from err
        return data if isinstance(data, dict) else {}

    async def _status(self, page: str) -> dict[str, Any]:
        """Read one status page."""
        return await self._json({"a": page})

    async def _command(self, cmd: str, *params: Any) -> None:
        query: dict[str, Any] = {"a": "command", "cmd": cmd}
        for index, value in enumerate(params, start=1):
            query[f"p{index}"] = value
        await self._json(query)

    # --- Reading ----------------------------------------------------------
    async def async_get_info(self) -> dict[str, str]:
        """Model, serial number, firmware, MAC and host name from the web page."""
        async with self._lock:
            page = await self._get("")
        info: dict[str, str] = {}
        for field, key in _PAGE_FIELDS.items():
            if match := re.search(rf"\b{field}='([^']*)'", page):
                info[key] = match.group(1).strip()
        if "mac" in info:
            info["mac"] = info["mac"].lower()
        if not info.get("model"):
            raise CrestronHdMdError("Device did not answer like an HD-MD switcher")
        return info

    async def async_get_state(self) -> dict[str, Any]:
        """Routes, names and signal states.

        Returns:
            routes         input routed to each output (0 = none), by output
            input_names    name of each input
            output_names   name of each output
            output_formats what each output reports sending, e.g. "No Source"
            input_sync     True where an input sees a signal
            output_sync    True where an output has a display connected
            output_enabled True where an output is enabled
        """
        async with self._lock:
            rout = await self._status("rout")
            inputs = await self._status("input")
            outputs = await self._status("outp")
        routes = rout.get("route")
        if not isinstance(routes, list) or not routes:
            raise CrestronHdMdError("The switcher sent no routing information")
        input_names = [str(n) for n in rout.get("in_name") or inputs.get("in_name") or []]
        output_names = [
            str(n) for n in rout.get("out_name") or outputs.get("out_name") or []
        ]
        return {
            "routes": [int(r) for r in routes],
            "input_names": input_names,
            "output_names": output_names,
            "output_formats": [str(v) for v in rout.get("out_timg") or []],
            "input_sync": [bool(v) for v in inputs.get("in_sync") or []],
            "output_sync": [bool(v) for v in outputs.get("out_sync") or []],
            "output_enabled": [bool(v) for v in outputs.get("cro") or []],
        }

    # --- Control ----------------------------------------------------------
    async def async_set_route(
        self, output: int, input_number: int, inputs: int, outputs: int
    ) -> None:
        """Route an input (0 = none) to an output; both are numbered from 1.

        The switcher stores whatever number it is given, so the range is
        checked here.
        """
        if not 1 <= output <= outputs:
            raise ValueError(f"Output {output} does not exist")
        if not 0 <= input_number <= inputs:
            raise ValueError(f"Input {input_number} does not exist")
        async with self._lock:
            await self._command(output_command(output), input_number)

    async def async_set_output_enabled(self, output: int, enabled: bool) -> None:
        """Enable or disable an output (numbered from 1)."""
        async with self._lock:
            await self._command("OUTENABLE", output - 1, 1 if enabled else 0)
