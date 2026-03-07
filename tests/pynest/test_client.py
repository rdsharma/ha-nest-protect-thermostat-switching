"""Tests for NestClient."""
import asyncio
from unittest.mock import patch

from aiohttp import web
import pytest


@pytest.mark.enable_socket
async def test_get_access_token_from_cookies_success(
    socket_enabled, aiohttp_client, pynest_import
):
    """Test getting an access token."""
    NestClient = pynest_import("client").NestClient

    async def make_token_response(request):
        return web.json_response(
            {
                "token_type": "Bearer",
                "access_token": "new-access-token",
                "scope": "The scope",
                "login_hint": "login-hint",
                "expires_in": 3600,
                "id_token": "",
                "session_state": {"prop": "value"},
            }
        )

    app = web.Application()
    app.router.add_get("/issue-token", make_token_response)
    client = await aiohttp_client(app)

    nest_client = NestClient(client)
    auth = await nest_client.get_access_token_from_cookies("issue-token", "cookies")
    assert auth.access_token == "new-access-token"


@pytest.mark.enable_socket
async def test_get_access_token_from_cookies_error(
    socket_enabled, aiohttp_client, pynest_import
):
    """Test failure while getting an access token."""
    NestClient = pynest_import("client").NestClient

    async def make_token_response(request):
        return web.json_response(
            {"error": "invalid_grant"}, headers=None, content_type="application/json"
        )

    app = web.Application()
    app.router.add_get("/issue-token", make_token_response)
    client = await aiohttp_client(app)

    nest_client = NestClient(client)
    with pytest.raises(Exception, match="invalid_grant"):
        await nest_client.get_access_token_from_cookies("issue-token", "cookies")


@pytest.mark.enable_socket
async def test_get_first_data_success(socket_enabled, aiohttp_client, pynest_import):
    """Test getting initial data from the API."""
    client_module = pynest_import("client")
    const_module = pynest_import("const")
    NestClient = client_module.NestClient
    NEST_REQUEST = const_module.NEST_REQUEST

    async def api_response(request):
        json = await request.json()
        request.app["request"].append((request.headers, json))
        return web.json_response(
            {
                "updated_buckets": [],
                "service_urls": {
                    "urls": {
                        "rubyapi_url": "https://home.nest.com/",
                        "czfe_url": "https://xxxx.transport.home.nest.com",
                        "log_upload_url": "https://logsink.home.nest.com/upload/user",
                        "transport_url": "https://xxxx.transport.home.nest.com",
                        "weather_url": "https://apps-weather.nest.com/weather/v1?query=",
                        "support_url": "https://nest.secure.force.com/support/webapp?",
                        "direct_transport_url": "https://xxx.transport.home.nest.com:443",
                    },
                    "limits": {
                        "thermostats_per_structure": 20,
                        "structures": 5,
                        "smoke_detectors_per_structure": 18,
                        "smoke_detectors": 54,
                        "thermostats": 60,
                    },
                    "weave": {
                        "service_config": "xxxx",
                        "pairing_token": "xxxx",
                        "access_token": "xxxx",
                    },
                },
                "weather_for_structures": {},
                "2fa_enabled": False,
            }
        )

    app = web.Application()
    app.router.add_post("/api/0.1/user/example-user/app_launch", api_response)
    app["request"] = []
    client = await aiohttp_client(app)

    nest_client = NestClient(client)
    with patch(
        "custom_components.nest_protect.pynest.client.APP_LAUNCH_URL_FORMAT",
        "/api/0.1/user/{user_id}/app_launch",
    ):
        result = await nest_client.get_first_data("access-token", "example-user")

    assert len(app["request"]) == 1
    (headers, json_request) = app["request"][0]
    assert headers.get("Authorization") == "Basic access-token"
    assert headers.get("X-nl-user-id") == "example-user"
    assert json_request == NEST_REQUEST
    assert result.updated_buckets == []
    assert result.service_urls["urls"]["transport_url"] == "https://xxxx.transport.home.nest.com"


async def test_bootstrap_remote_comfort_sensing_collects_latest_update_per_thermostat(
    pynest_import, monkeypatch
):
    """Bootstrap should retain the latest update seen for each thermostat."""
    client_module = pynest_import("client")
    protocol = pynest_import("thermostat_protocol")
    NestClient = client_module.NestClient

    first = protocol.RemoteComfortSensingObserveUpdate(
        thermostat_id="DEVICE_CCA7C1000022A6CF",
        trait_label=protocol.REMOTE_COMFORT_SENSING_TRAIT_LABEL,
        settings=protocol.RemoteComfortSensingSettings(
            rcs_control_mode=1,
            source_type=protocol.RCS_SOURCE_TYPE_SENSOR,
            active_sensor_id="DEVICE_18B430CE7E5A5C06",
            associated_sensors=(),
            remembered_sensor_id="DEVICE_18B430CE7E5A5C06",
            raw_payload=b"sensor",
        ),
    )
    second = protocol.RemoteComfortSensingObserveUpdate(
        thermostat_id="DEVICE_CCA7C1000022A6CF",
        trait_label=protocol.REMOTE_COMFORT_SENSING_TRAIT_LABEL,
        settings=protocol.RemoteComfortSensingSettings(
            rcs_control_mode=1,
            source_type=protocol.RCS_SOURCE_TYPE_THERMOSTAT,
            active_sensor_id=None,
            associated_sensors=(),
            remembered_sensor_id="DEVICE_18B430CE7E5A5C06",
            raw_payload=b"thermostat",
        ),
    )

    nest_client = NestClient(session=object())

    async def fake_observe(_access_token):
        yield first
        yield second
        await asyncio.sleep(3600)

    monkeypatch.setattr(nest_client, "observe_remote_comfort_sensing", fake_observe)

    updates = await nest_client.bootstrap_remote_comfort_sensing(
        "access-token", initial_timeout=0.01, settle_timeout=0.01
    )

    assert len(updates) == 1
    assert updates[0].settings.source_type == protocol.RCS_SOURCE_TYPE_THERMOSTAT
    assert updates[0].settings.active_sensor_id is None
