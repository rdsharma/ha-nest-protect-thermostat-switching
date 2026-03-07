"""Config flow tests for thermostat pairing options."""

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nest_protect import HomeAssistantNestProtectData
from custom_components.nest_protect.config_flow import OptionsFlowHandler
from custom_components.nest_protect.const import CONF_THERMOSTAT_LINKS, DOMAIN
from custom_components.nest_protect.pynest.models import ThermostatData
from custom_components.nest_protect.thermostat import OfficialThermostatCandidate


@pytest.mark.parametrize("label_change", ["Master Bedroom", "Primary Bedroom"])
async def test_options_flow_uses_stable_thermostat_field_keys(
    hass, label_change: str
) -> None:
    """The pairing flow should survive thermostat label changes."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"refresh_token": "token"})
    config_entry.add_to_hass(hass)

    thermostat = ThermostatData(
        device_id="DEVICE_CCA7C1000022A6CF",
        name="Master Bedroom",
        where_name="Master Bedroom",
        where_id=None,
        structure_id=None,
    )
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = HomeAssistantNestProtectData(
        devices={},
        areas={},
        client=object(),
        thermostats={thermostat.device_id: thermostat},
    )

    flow = OptionsFlowHandler(config_entry)
    flow.hass = hass

    official_candidates = {
        "nest\x1fofficial-id": OfficialThermostatCandidate(
            device_entry_id="device-entry-id",
            device_identifier=("nest", "official-id"),
            device_identifier_key="nest\x1fofficial-id",
            name="Master Bedroom",
            area_name="Master Bedroom",
        )
    }

    with patch(
        "custom_components.nest_protect.config_flow.async_official_thermostats",
        return_value=official_candidates,
    ):
        result = await flow.async_step_init()

        assert result["type"] is FlowResultType.FORM
        field = next(iter(result["data_schema"].schema))
        field_key = field.schema

        thermostat.name = label_change

        result = await flow.async_step_init({field_key: "nest\x1fofficial-id"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_THERMOSTAT_LINKS] == {
        "DEVICE_CCA7C1000022A6CF": "nest\x1fofficial-id"
    }
