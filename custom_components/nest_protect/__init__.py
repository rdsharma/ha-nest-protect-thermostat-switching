"""Nest Protect integration."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field

from aiohttp import ClientConnectorError, ClientError, ServerDisconnectedError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_ACCOUNT_TYPE,
    CONF_COOKIES,
    CONF_ISSUE_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_THERMOSTAT_LINKS,
    DOMAIN,
    LOGGER,
    PLATFORMS,
)
from .pynest.client import NestClient
from .pynest.const import NEST_ENVIRONMENTS
from .pynest.enums import BucketType, Environment
from .pynest.exceptions import (
    BadCredentialsException,
    EmptyResponseException,
    NestServiceException,
    NotAuthenticatedException,
    PynestException,
)
from .pynest.models import (
    Bucket,
    FirstDataAPIResponse,
    ThermostatData,
    TopazBucket,
    WhereBucketValue,
)
from .thermostat import (
    apply_remote_comfort_sensing,
    async_official_thermostats,
    build_thermostats,
    build_thermostats_from_observe,
    thermostat_update_signal,
)


@dataclass
class HomeAssistantNestProtectData:
    """Nest Protect data stored in the Home Assistant data object."""

    devices: dict[str, Bucket]
    areas: dict[str, str]
    client: NestClient
    thermostats: dict[str, ThermostatData] = field(default_factory=dict)
    subscription_task: asyncio.Task | None = None
    observe_task: asyncio.Task | None = None


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Migrate old Config entries."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_ACCOUNT_TYPE: Environment.PRODUCTION},
            version=2,
        )

    LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Nest Protect from a config entry."""
    issue_token = None
    cookies = None
    refresh_token = None

    if CONF_ISSUE_TOKEN in entry.data and CONF_COOKIES in entry.data:
        issue_token = entry.data[CONF_ISSUE_TOKEN]
        cookies = entry.data[CONF_COOKIES]
    if CONF_REFRESH_TOKEN in entry.data:
        refresh_token = entry.data[CONF_REFRESH_TOKEN]

    session = async_create_clientsession(hass)
    account_type = entry.data[CONF_ACCOUNT_TYPE]
    client = NestClient(session=session, environment=NEST_ENVIRONMENTS[account_type])

    try:
        # Using user-retrieved cookies for authentication
        if issue_token and cookies:
            auth = await client.get_access_token_from_cookies(issue_token, cookies)
        # Using refresh_token from legacy authentication method
        elif refresh_token:
            auth = await client.get_access_token_from_refresh_token(refresh_token)

        nest = await client.authenticate(auth.access_token)
    except (TimeoutError, ClientError) as exception:
        raise ConfigEntryNotReady from exception
    except BadCredentialsException as exception:
        raise ConfigEntryAuthFailed from exception
    except Exception as exception:  # pylint: disable=broad-except
        LOGGER.exception("Unknown exception.")
        raise ConfigEntryNotReady from exception

    data = await client.get_first_data(nest.access_token, nest.userid)
    bucket_counts = Counter(bucket.type for bucket in data.updated_buckets)
    LOGGER.debug("App launch bucket counts: %s", dict(bucket_counts))

    device_buckets: list[Bucket] = []
    areas: dict[str, str] = {}

    for bucket in data.updated_buckets:
        # Nest Protect
        if bucket.type == BucketType.TOPAZ:
            device_buckets.append(bucket)
        # Temperature Sensors
        elif bucket.type == BucketType.KRYPTONITE:
            device_buckets.append(bucket)

        # Areas
        if bucket.type == BucketType.WHERE and isinstance(
            bucket.value, WhereBucketValue
        ):
            bucket_value = bucket.value
            for area in bucket_value.wheres:
                areas[area.where_id] = area.name

    devices: dict[str, Bucket] = {b.object_key: b for b in device_buckets}
    official_thermostats = async_official_thermostats(hass)
    thermostats = build_thermostats(
        data.updated_buckets,
        areas,
        official_thermostats,
        entry.options.get(CONF_THERMOSTAT_LINKS),
    )
    if not thermostats:
        try:
            observe_updates = await client.bootstrap_remote_comfort_sensing(
                nest.access_token
            )
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.debug("Observe bootstrap failed: %s", exception)
        else:
            thermostats = build_thermostats_from_observe(
                observe_updates,
                devices,
                areas,
                official_thermostats,
                entry.options.get(CONF_THERMOSTAT_LINKS),
            )
    LOGGER.debug(
        "Discovered %s unofficial thermostats from %s device buckets and %s rcs_settings buckets; %s official Nest thermostat candidates",
        len(thermostats),
        bucket_counts.get(BucketType.DEVICE, 0),
        bucket_counts.get(BucketType.RCS_SETTINGS, 0),
        len(official_thermostats),
    )

    entry_data = HomeAssistantNestProtectData(
        devices=devices,
        areas=areas,
        client=client,
        thermostats=thermostats,
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Subscribe for real-time updates
    entry_data.subscription_task = asyncio.create_task(
        _async_subscribe_for_data(hass, entry, data)
    )
    if thermostats:
        entry_data.observe_task = asyncio.create_task(
            _async_observe_thermostats(hass, entry)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cancel subscription task only after successful platform unload
        if entry.entry_id in hass.data.get(DOMAIN, {}):
            entry_data: HomeAssistantNestProtectData = hass.data[DOMAIN][entry.entry_id]
            if entry_data.subscription_task:
                entry_data.subscription_task.cancel()
                try:
                    await entry_data.subscription_task
                except asyncio.CancelledError:
                    # Task cancellation is expected during unload; ignore.
                    pass
            if entry_data.observe_task:
                entry_data.observe_task.cancel()
                try:
                    await entry_data.observe_task
                except asyncio.CancelledError:
                    pass
            hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def _register_subscribe_task(
    hass: HomeAssistant, entry: ConfigEntry, data: FirstDataAPIResponse
) -> asyncio.Task | None:
    """Create a new subscription task and update the reference."""
    # Check if entry is still loaded before creating new task
    if entry.entry_id not in hass.data.get(DOMAIN, {}):
        return None

    entry_data: HomeAssistantNestProtectData = hass.data[DOMAIN][entry.entry_id]
    task = asyncio.create_task(_async_subscribe_for_data(hass, entry, data))
    entry_data.subscription_task = task
    return task


async def _async_subscribe_for_data(
    hass: HomeAssistant, entry: ConfigEntry, data: FirstDataAPIResponse
):
    """Subscribe for new data."""
    # Check if entry is still loaded
    if entry.entry_id not in hass.data.get(DOMAIN, {}):
        return

    entry_data: HomeAssistantNestProtectData = hass.data[DOMAIN][entry.entry_id]

    try:
        # Check for cancellation early to avoid creating orphaned tasks
        # if the entry is being unloaded
        await asyncio.sleep(0)
        # TODO move refresh token logic to client
        if (
            not entry_data.client.nest_session
            or entry_data.client.nest_session.is_expired()
        ):
            LOGGER.debug("Subscriber: authenticate for new Nest session")

        if not entry_data.client.auth or entry_data.client.auth.is_expired():
            LOGGER.debug("Subscriber: retrieving new Google access token")
            auth = await entry_data.client.get_access_token()
            entry_data.client.nest_session = await entry_data.client.authenticate(
                auth.access_token
            )

        # Subscribe to Google Nest subscribe endpoint
        result = await entry_data.client.subscribe_for_data(
            entry_data.client.nest_session.access_token,
            entry_data.client.nest_session.userid,
            data.service_urls["urls"]["transport_url"],
            data.updated_buckets,
        )

        # TODO write this data away in a better way, best would be to directly model API responses in client
        for bucket in result["objects"]:
            key = bucket["object_key"]

            # Nest Protect
            if key.startswith("topaz."):
                topaz = TopazBucket(**bucket)
                entry_data.devices[key] = topaz

                # TODO investigate if we want to use dispatcher, or get data from entry data in sensors
                async_dispatcher_send(hass, key, topaz)

            # Areas
            if key.startswith("where."):
                bucket_value = Bucket(**bucket).value

                for area in bucket_value["wheres"]:
                    entry_data.areas[area["where_id"]] = area["name"]

            # Temperature Sensors
            if key.startswith("kryptonite."):
                kryptonite = Bucket(**bucket)
                entry_data.devices[key] = kryptonite

                async_dispatcher_send(hass, key, kryptonite)

        # Update buckets with new data, to only receive new updates
        buckets = {d["object_key"]: d for d in result["objects"]}

        LOGGER.debug(buckets)

        objects = [
            dict(vars(b), **buckets.get(b.object_key, {})) for b in data.updated_buckets
        ]

        data.updated_buckets = [
            Bucket(
                object_key=bucket["object_key"],
                object_revision=bucket["object_revision"],
                object_timestamp=bucket["object_timestamp"],
                value=bucket["value"],
                type=bucket["type"],
            )
            for bucket in objects
        ]

        _register_subscribe_task(hass, entry, data)
    except ServerDisconnectedError:
        LOGGER.debug("Subscriber: server disconnected.")
        _register_subscribe_task(hass, entry, data)

    except asyncio.exceptions.TimeoutError:
        LOGGER.debug("Subscriber: session timed out.")
        _register_subscribe_task(hass, entry, data)

    except ClientConnectorError:
        LOGGER.debug("Subscriber: cannot connect to host.")
        _register_subscribe_task(hass, entry, data)

    except EmptyResponseException:
        LOGGER.debug("Subscriber: Nest Service sent empty response.")
        _register_subscribe_task(hass, entry, data)

    except NotAuthenticatedException:
        LOGGER.debug("Subscriber: 401 exception.")
        # Renewing access token
        await entry_data.client.get_access_token()
        await entry_data.client.authenticate(entry_data.client.auth.access_token)
        _register_subscribe_task(hass, entry, data)

    except BadCredentialsException as exception:
        LOGGER.debug(
            "Bad credentials detected. Please re-authenticate the Nest Protect integration."
        )
        raise ConfigEntryAuthFailed from exception

    except NestServiceException:
        LOGGER.debug("Subscriber: Nest Service error. Updates paused for 2 minutes.")

        await asyncio.sleep(60 * 2)
        _register_subscribe_task(hass, entry, data)

    except PynestException:
        LOGGER.exception(
            "Unknown pynest exception. Please create an issue on GitHub with your logfile. Updates paused for 1 minute."
        )

        # Wait a minute before retrying
        await asyncio.sleep(60)
        _register_subscribe_task(hass, entry, data)

    except asyncio.CancelledError:
        # Task is being cancelled during unload; do not register a new task
        LOGGER.debug("Subscriber: task cancelled, stopping subscription.")
        raise

    except Exception:  # pylint: disable=broad-except
        # Wait 5 minutes before retrying
        await asyncio.sleep(60 * 5)
        _register_subscribe_task(hass, entry, data)

        LOGGER.exception(
            "Unknown exception. Please create an issue on GitHub with your logfile. Updates paused for 5 minutes."
        )


async def _async_observe_thermostats(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Observe thermostat remote comfort sensing state."""
    while entry.entry_id in hass.data.get(DOMAIN, {}):
        entry_data: HomeAssistantNestProtectData = hass.data[DOMAIN][entry.entry_id]

        try:
            nest_session = await entry_data.client.ensure_authenticated()
            async for update in entry_data.client.observe_remote_comfort_sensing(
                nest_session.access_token
            ):
                if entry.entry_id not in hass.data.get(DOMAIN, {}):
                    return

                thermostat = entry_data.thermostats.get(update.thermostat_id)
                if thermostat is None:
                    continue

                apply_remote_comfort_sensing(
                    thermostat,
                    update.settings,
                    entry_data.devices,
                    entry_data.areas,
                )
                async_dispatcher_send(
                    hass,
                    thermostat_update_signal(thermostat.device_id),
                    thermostat,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.debug("Thermostat observe reconnect after error: %s", exception)
            await asyncio.sleep(5)
        else:
            await asyncio.sleep(1)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return True
