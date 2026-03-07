"""Constants for Nest Protect."""

from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

LOGGER: logging.Logger = logging.getLogger(__package__)

DOMAIN: Final = "nest_protect"
ATTRIBUTION: Final = "Data provided by Google"

CONF_ACCOUNT_TYPE: Final = "account_type"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_ISSUE_TOKEN: Final = "issue_token"
CONF_COOKIES: Final = "cookies"
CONF_THERMOSTAT_LINKS: Final = "thermostat_links"
NEST_DOMAIN: Final = "nest"
SERVICE_SET_FAN_TIMER: Final = "set_fan_timer"
ATTR_DURATION_MINUTES: Final = "duration_minutes"
ATTR_SELECT_ENTITY: Final = "select_entity"
ATTR_THERMOSTAT_ID: Final = "thermostat_id"
THERMOSTAT_UPDATE_SIGNAL_PREFIX: Final = f"{DOMAIN}_thermostat_"
THERMOSTAT_DISCOVERY_SIGNAL_PREFIX: Final = f"{DOMAIN}_thermostat_discovered_"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
]
