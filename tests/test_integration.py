"""Set the integration up inside Home Assistant against the simulated switcher.

Skipped unless pytest-homeassistant-custom-component is installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from test_api import FakeSwitcher  # noqa: E402

DOMAIN = "crestron_hd_md"
OUT1 = "select.av_switcher_output_1_source"
OUT2 = "select.av_switcher_output_2_source"


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations):
    """Load custom_components."""


@pytest.fixture
async def fake():
    switcher = FakeSwitcher()
    runner = await switcher.start()
    yield switcher
    await runner.cleanup()


async def _add(hass: HomeAssistant, fake: FakeSwitcher):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "form"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": f"127.0.0.1:{fake.port}", "name": "AV switcher"},
    )


async def test_config_flow_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "127.0.0.1:9"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entities_and_routing(hass: HomeAssistant, fake: FakeSwitcher) -> None:
    result = await _add(hass, fake)
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.unique_id == "00:10:7f:62:0a:cd"
    assert entry.data["model"] == "HD-MD4x2-4K-E"

    out1 = hass.states.get(OUT1)
    assert out1.state == "INPUT1"
    assert out1.attributes["options"] == ["INPUT1", "INPUT2", "INPUT3", "INPUT4", "None"]
    assert out1.attributes["output_name"] == "OUTPUT1"
    assert out1.attributes["output_format"] == "1920x1080@60"
    assert hass.states.get("switch.av_switcher_output_2_enabled").state == "on"
    assert hass.states.get("binary_sensor.av_switcher_input_2_signal").state == "on"
    assert hass.states.get("binary_sensor.av_switcher_input_1_signal").state == "off"
    assert hass.states.get("binary_sensor.av_switcher_output_1_display").state == "on"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": OUT2, "option": "INPUT3"}, blocking=True
    )
    assert fake.route == [1, 3]
    assert hass.states.get(OUT2).state == "INPUT3"

    await hass.services.async_call(
        "select", "select_option", {"entity_id": OUT1, "option": "None"}, blocking=True
    )
    assert fake.route == [0, 3]
    assert hass.states.get(OUT1).state == "None"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.av_switcher_output_2_enabled"}, blocking=True
    )
    assert fake.cro == [1, 0]

    # Route by number through the action.
    await hass.services.async_call(
        DOMAIN, "select_input", {"entity_id": OUT1, "input": 4}, blocking=True
    )
    assert fake.route == [4, 3]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN, "select_input", {"entity_id": OUT1, "input": 5}, blocking=True
        )
    assert fake.route == [4, 3]

    # Renaming an input on the switcher renames the option.
    fake.in_name[3] = "Laptop"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(OUT1).state == "Laptop"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
