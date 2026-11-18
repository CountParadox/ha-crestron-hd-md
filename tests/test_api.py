"""Tests for the client against a simulated HD-MD4x2-4K-E web interface."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import aiohttp
from aiohttp import web
import pytest

# Load api.py on its own so these tests do not need Home Assistant installed.
_SPEC = importlib.util.spec_from_file_location(
    "crestron_hd_md_api",
    Path(__file__).parents[1] / "custom_components" / "crestron_hd_md" / "api.py",
)
api = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = api
_SPEC.loader.exec_module(api)

PAGE = """<!DOCTYPE html><html><head><title>HD-MD4x2-4K-E</title><script>
model='HD-MD4x2-4K-E';seriv='13315492';firmv='1.0.0.2162';ip_mode=0;host='HDMD4X2-620ACD';
domain='crestron.crestron.com';ip='192.168.0.10';mac='00:10:7F:62:0A:CD';login_ur=1;
</script></head><body></body></html>"""


class FakeSwitcher:
    """Behaves like the real unit's aj.html.

    Like the real unit it answers and obeys whether or not anybody is logged
    in; by default nobody is (login_ur 0).
    """

    def __init__(self) -> None:
        self.logged_in = False
        self.route = [1, 1]
        self.in_name = ["INPUT1", "INPUT2", "INPUT3", "INPUT4"]
        self.out_name = ["OUTPUT1", "OUTPUT2"]
        self.in_sync = [0, 1, 0, 0]
        self.out_sync = [1, 0]
        self.cro = [1, 1]
        self.commands: list[dict[str, str]] = []
        self.port = 0

    async def page(self, request: web.Request) -> web.Response:
        return web.Response(text=PAGE, content_type="text/html")

    async def aj(self, request: web.Request) -> web.Response:
        query = dict(request.query)
        level = 1 if self.logged_in else 0
        action = query.get("a")
        if action == "command":
            self.commands.append(query)
            cmd = query.get("cmd", "")
            if len(cmd) == 1 and cmd in "AB":
                # Like the real unit: stores whatever number it is given.
                self.route["AB".index(cmd)] = int(query.get("p1", 83))
            elif cmd == "OUTENABLE":
                self.cro[int(query["p1"])] = int(query["p2"])
            return web.Response(text="")
        if action == "rout":
            return web.json_response(
                {
                    "login_ur": level,
                    "out_timg": ["1920x1080@60", "No Source"],
                    "out_name": self.out_name,
                    "route": self.route,
                    "in_name": self.in_name,
                }
            )
        if action == "input":
            return web.json_response(
                {"login_ur": level, "in_sync": self.in_sync, "in_name": self.in_name}
            )
        if action == "outp":
            return web.json_response(
                {
                    "login_ur": level,
                    "route": self.route,
                    "out_sync": self.out_sync,
                    "out_name": self.out_name,
                    "cro": self.cro,
                }
            )
        return web.json_response({"login_ur": level})

    async def start(self) -> web.AppRunner:
        app = web.Application()
        app.router.add_get("/", self.page)
        app.router.add_get("/aj.html", self.aj)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        self.port = runner.addresses[0][1]
        return runner


@pytest.fixture
async def switcher():
    fake = FakeSwitcher()
    runner = await fake.start()
    async with aiohttp.ClientSession() as session:
        yield fake, session
    await runner.cleanup()


def client_for(fake, session):
    return api.CrestronHdMdClient(session, f"127.0.0.1:{fake.port}")


async def test_info(switcher):
    fake, session = switcher
    info = await client_for(fake, session).async_get_info()
    assert info == {
        "model": "HD-MD4x2-4K-E",
        "serial": "13315492",
        "firmware": "1.0.0.2162",
        "mac": "00:10:7f:62:0a:cd",
        "hostname": "HDMD4X2-620ACD",
    }


async def test_state(switcher):
    fake, session = switcher
    state = await client_for(fake, session).async_get_state()
    assert state["routes"] == [1, 1]
    assert state["input_names"] == ["INPUT1", "INPUT2", "INPUT3", "INPUT4"]
    assert state["output_names"] == ["OUTPUT1", "OUTPUT2"]
    assert state["input_sync"] == [False, True, False, False]
    assert state["output_sync"] == [True, False]
    assert state["output_enabled"] == [True, True]
    assert state["output_formats"] == ["1920x1080@60", "No Source"]


async def test_route_and_range_check(switcher):
    fake, session = switcher
    client = client_for(fake, session)
    await client.async_set_route(2, 3, inputs=4, outputs=2)
    assert fake.route == [1, 3]
    assert fake.commands[-1] == {"a": "command", "cmd": "B", "p1": "3"}
    await client.async_set_route(1, 0, inputs=4, outputs=2)
    assert fake.route == [0, 3]
    # The unit would store these, so they must never be sent.
    sent = len(fake.commands)
    with pytest.raises(ValueError):
        await client.async_set_route(1, 5, inputs=4, outputs=2)
    with pytest.raises(ValueError):
        await client.async_set_route(3, 1, inputs=4, outputs=2)
    assert len(fake.commands) == sent


async def test_output_enable(switcher):
    fake, session = switcher
    client = client_for(fake, session)
    await client.async_set_output_enabled(2, False)
    assert fake.cro == [1, 0]
    assert fake.commands[-1]["p1"] == "1"


async def test_never_logs_in(switcher):
    fake, session = switcher
    client = client_for(fake, session)
    await client.async_get_state()
    await client.async_set_route(1, 2, inputs=4, outputs=2)
    assert fake.route == [2, 1]
    assert not any(c.get("cmd") == "check_login" for c in fake.commands)


async def test_unreachable():
    async with aiohttp.ClientSession() as session:
        client = api.CrestronHdMdClient(session, "127.0.0.1:9", timeout=1.0)
        with pytest.raises(api.CrestronHdMdConnectionError):
            await client.async_get_state()


def test_output_command():
    assert api.output_command(1) == "A"
    assert api.output_command(2) == "B"
