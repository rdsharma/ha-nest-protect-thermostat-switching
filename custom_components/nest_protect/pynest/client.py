"""PyNest API Client."""

from __future__ import annotations

import asyncio
import logging
from random import randint
import time
from types import TracebackType
from typing import Any, AsyncIterator, cast
from uuid import uuid4

from aiohttp import ClientSession, ClientTimeout, ContentTypeError, FormData

from .const import (
    APP_LAUNCH_URL_FORMAT,
    DEFAULT_NEST_ENVIRONMENT,
    GRPC_BATCH_UPDATE_ENDPOINT,
    GRPC_OBSERVE_ENDPOINT,
    NEST_AUTH_URL_JWT,
    NEST_GRPC_WEBAPP_VERSION,
    NEST_REQUEST,
    TOKEN_URL,
    USER_AGENT,
)
from .exceptions import (
    BadCredentialsException,
    BadGatewayException,
    EmptyResponseException,
    GatewayTimeoutException,
    NotAuthenticatedException,
    PynestException,
)
from .models import (
    Bucket,
    FirstDataAPIResponse,
    GoogleAuthResponse,
    GoogleAuthResponseForCookies,
    NestAuthResponse,
    NestEnvironment,
    NestResponse,
    RemoteComfortSensingSettings,
)
from .thermostat_protocol import (
    REMOTE_COMFORT_SENSING_OBSERVE_TYPE,
    decode_observe_buffer,
    decode_remote_comfort_sensing_settings,
    encode_batch_update_state_request,
    encode_observe_request,
    RemoteComfortSensingObserveUpdate,
    update_remote_comfort_sensing_payload,
)

_LOGGER = logging.getLogger(__package__)


class NestClient:
    """Interface class for the Nest API."""

    nest_session: NestResponse | None = None
    auth: GoogleAuthResponseForCookies | None = None
    session: ClientSession
    transport_url: str | None = None
    environment: NestEnvironment

    # Legacy Auth
    refresh_token: str | None = None
    # Cookie Auth
    cookies: str | None = None
    issue_token: str | None = None

    def __init__(
        self,
        session: ClientSession | None = None,
        # refresh_token: str | None = None,
        # issue_token: str | None = None,
        # cookies: str | None = None,
        environment: NestEnvironment = DEFAULT_NEST_ENVIRONMENT,
    ) -> None:
        """Initialize NestClient."""

        self.session = session if session else ClientSession()
        # self.refresh_token = refresh_token
        # self.issue_token = issue_token
        # self.cookies = cookies
        self.environment = environment

    async def __aenter__(self) -> NestClient:
        """__aenter__."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """__aexit__."""
        await self.session.close()

    async def get_access_token(self) -> GoogleAuthResponse:
        """Get a Nest access token."""

        if self.refresh_token:
            await self.get_access_token_from_refresh_token(self.refresh_token)
        elif self.issue_token and self.cookies:
            await self.get_access_token_from_cookies(self.issue_token, self.cookies)

        return self.auth

    async def get_access_token_from_refresh_token(
        self, refresh_token: str | None = None
    ) -> GoogleAuthResponse:
        """Get a Nest refresh token from an authorization code."""

        if refresh_token:
            self.refresh_token = refresh_token

        if not self.refresh_token:
            raise Exception("No refresh token")

        async with self.session.post(
            TOKEN_URL,
            data=FormData(
                {
                    "refresh_token": self.refresh_token,
                    "client_id": self.environment.client_id,
                    "grant_type": "refresh_token",
                }
            ),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        ) as response:
            result = await response.json()

            if "error" in result:
                if result["error"] == "invalid_grant":
                    raise BadCredentialsException(result["error"])

                raise Exception(result["error"])

            self.auth = GoogleAuthResponse(**result)

            return self.auth

    async def get_access_token_from_cookies(
        self, issue_token: str, cookies: str
    ) -> GoogleAuthResponse:
        """Get a Nest refresh token from an issue token and cookies."""

        if issue_token:
            self.issue_token = issue_token

        if cookies:
            self.cookies = cookies

        async with self.session.get(
            issue_token,
            headers={
                "Sec-Fetch-Mode": "cors",
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XmlHttpRequest",
                "Referer": "https://accounts.google.com/o/oauth2/iframe",
                "cookie": cookies,
            },
        ) as response:
            result = await response.json()

            if "error" in result:
                # Cookie method
                if result["error"] == "USER_LOGGED_OUT":
                    raise BadCredentialsException(
                        f"{result["error"]} - {result["detail"]}"
                    )

                raise Exception(result["error"])

            self.auth = GoogleAuthResponseForCookies(**result)

            return self.auth

    async def authenticate(self, access_token: str) -> NestResponse:
        """Start a new Nest session with an access token."""

        async with self.session.post(
            NEST_AUTH_URL_JWT,
            data=FormData(
                {
                    "embed_google_oauth_access_token": True,
                    "expire_after": "3600s",
                    "google_oauth_access_token": access_token,
                    "policy_id": "authproxy-oauth-policy",
                }
            ),
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": USER_AGENT,
                "Referer": self.environment.host,
            },
        ) as response:
            result = await response.json()
            nest_auth = NestAuthResponse(**result)

        async with self.session.get(
            self.environment.host + "/session",
            headers={
                "Authorization": f"Basic {nest_auth.jwt}",
                "cookie": "G_ENABLED_IDPS=google; eu_cookie_accepted=1; viewer-volume=0.5; cztoken="
                + (nest_auth.jwt if nest_auth.jwt else ""),
            },
        ) as response:
            try:
                nest_response = await response.json()
            except ContentTypeError as exception:
                nest_response = await response.text()

                raise PynestException(
                    f"{response.status} error while authenticating - {nest_response}. Please create an issue on GitHub."
                ) from exception

            # Change variable names since Python cannot handle vars that start with a number
            if nest_response.get("2fa_state"):
                nest_response["_2fa_state"] = nest_response.pop("2fa_state")
            if nest_response.get("2fa_enabled"):
                nest_response["_2fa_enabled"] = nest_response.pop("2fa_enabled")
            if nest_response.get("2fa_state_changed"):
                nest_response["_2fa_state_changed"] = nest_response.pop(
                    "2fa_state_changed"
                )

            if nest_response.get("error"):
                _LOGGER.error("Authentication error: %s", nest_response.get("error"))

                raise PynestException(
                    f"{response.status} error while authenticating - {nest_response}."
                )

            try:
                self.nest_session = NestResponse(**nest_response)
            except Exception as exception:
                nest_response = await response.text()

                if result.get("error"):
                    _LOGGER.error("Could not interpret Nest response")

                raise PynestException(
                    f"{response.status} error while authenticating - {nest_response}. Please create an issue on GitHub."
                ) from exception

            return self.nest_session

    async def ensure_authenticated(self) -> NestResponse:
        """Return a current Nest session, refreshing auth when required."""
        auth = self.auth
        if auth is None or auth.is_expired():
            auth = await self.get_access_token()

        if self.nest_session is None or self.nest_session.is_expired():
            self.nest_session = await self.authenticate(auth.access_token)

        return self.nest_session

    async def get_first_data(
        self, nest_access_token: str, user_id: str, request: dict = NEST_REQUEST
    ) -> FirstDataAPIResponse:
        """Get first data."""
        async with self.session.post(
            APP_LAUNCH_URL_FORMAT.format(host=self.environment.host, user_id=user_id),
            json=request,
            headers={
                "Authorization": f"Basic {nest_access_token}",
                "X-nl-user-id": user_id,
                "X-nl-protocol-version": str(1),
            },
        ) as response:
            result = await response.json()

            if "2fa_enabled" in result:
                result["_2fa_enabled"] = result.pop("2fa_enabled")

            if result.get("error"):
                _LOGGER.debug("Received error from Nest service", await response.text())

                raise PynestException(
                    f"{response.status} error while subscribing - {result}"
                )

            result = FirstDataAPIResponse(**result)

            self.transport_url = result.service_urls["urls"]["transport_url"]

            return result

    async def subscribe_for_data(
        self,
        nest_access_token: str,
        user_id: str,
        transport_url: str,
        updated_buckets: dict,
    ) -> Any:
        """Subscribe for data."""
        timeout = 600

        objects = []
        for bucket in updated_buckets:
            bucket = cast(Bucket, bucket)
            objects.append(
                {
                    "object_key": bucket.object_key,
                    "object_revision": bucket.object_revision,
                    "object_timestamp": bucket.object_timestamp,
                }
            )

        # TODO throw better exceptions
        async with self.session.post(
            f"{transport_url}/v6/subscribe",
            timeout=ClientTimeout(total=timeout),
            json={
                "objects": objects,
                # "timeout": timeout,
                # "sessionID": f"ios-${user_id}.{random}.{epoch}",
            },
            headers={
                "Authorization": f"Basic {nest_access_token}",
                "X-nl-user-id": user_id,
                "X-nl-protocol-version": str(1),
            },
        ) as response:
            _LOGGER.debug("Data received via subscriber (status: %s)", response.status)

            if response.status == 401:
                raise NotAuthenticatedException(await response.text())

            if response.status == 504:
                raise GatewayTimeoutException(await response.text())

            if response.status == 502:
                raise BadGatewayException(await response.text())

            if response.status == 200 and response.content_type == "text/plain":
                raise EmptyResponseException(await response.text())

            try:
                result = await response.json()
            except ContentTypeError as error:
                result = await response.text()

                raise PynestException(
                    f"{response.status} error while subscribing - {result}"
                ) from error

            # TODO type object
            return result

    async def observe_remote_comfort_sensing(
        self, nest_access_token: str
    ) -> AsyncIterator[RemoteComfortSensingObserveUpdate]:
        """Yield live thermostat remote comfort sensing updates."""
        request = encode_observe_request((REMOTE_COMFORT_SENSING_OBSERVE_TYPE,))
        headers = {
            "Authorization": f"Basic {nest_access_token}",
            "Content-Type": "application/x-protobuf",
            "Origin": self.environment.host,
            "Referer": f"{self.environment.host}/",
            "User-Agent": USER_AGENT,
            "request-id": str(uuid4()),
            "X-Accept-Content-Transfer-Encoding": "base64",
            "X-Accept-Response-Streaming": "true",
            "X-nl-webapp-version": NEST_GRPC_WEBAPP_VERSION,
        }

        async with self.session.post(
            f"{self.environment.grpc_host}{GRPC_OBSERVE_ENDPOINT}",
            data=request,
            headers=headers,
            timeout=ClientTimeout(total=None, sock_connect=30),
        ) as response:
            if response.status == 401:
                raise NotAuthenticatedException(await response.text())
            if response.status != 200:
                raise PynestException(
                    f"{response.status} error while observing - {await response.text()}"
                )

            buffer = b""
            async for chunk, end_of_http_chunk in response.content.iter_chunks():
                if not chunk:
                    continue

                buffer += chunk.strip()
                if not end_of_http_chunk:
                    continue

                updates, buffer = decode_observe_buffer(buffer)
                for update in updates:
                    yield update

    async def bootstrap_remote_comfort_sensing(
        self,
        nest_access_token: str,
        initial_timeout: float = 8.0,
        settle_timeout: float = 0.75,
    ) -> list[RemoteComfortSensingObserveUpdate]:
        """Collect an initial snapshot of remote comfort sensing updates."""
        updates: dict[str, RemoteComfortSensingObserveUpdate] = {}
        stream = self.observe_remote_comfort_sensing(nest_access_token)

        try:
            while True:
                timeout = settle_timeout if updates else initial_timeout
                update = await asyncio.wait_for(stream.__anext__(), timeout=timeout)
                updates[update.thermostat_id] = update
        except TimeoutError:
            return list(updates.values())
        except StopAsyncIteration:
            return list(updates.values())
        finally:
            await stream.aclose()

    async def update_objects(
        self,
        nest_access_token: str,
        user_id: str,
        transport_url: str,
        objects_to_update: dict,
    ) -> Any:
        """Subscribe for data."""

        epoch = int(time.time())
        random = str(randint(100, 999))

        # TODO throw better exceptions
        async with self.session.post(
            f"{transport_url}/v6/put",
            json={
                "session": f"ios-${user_id}.{random}.{epoch}",
                "objects": objects_to_update,
            },
            headers={
                "Authorization": f"Basic {nest_access_token}",
                "X-nl-user-id": user_id,
                "X-nl-protocol-version": str(1),
            },
        ) as response:
            if response.status == 401:
                raise NotAuthenticatedException(await response.text())

            try:
                result = await response.json()
            except ContentTypeError:
                result = await response.text()

                raise PynestException(
                    f"{response.status} error while subscribing - {result}"
                )

            # TODO type object

            return result

    async def async_set_active_temperature_sensor(
        self,
        thermostat_id: str,
        current_settings: RemoteComfortSensingSettings,
        target_sensor_id: str | None,
    ) -> RemoteComfortSensingSettings:
        """Set the active temperature sensor for a thermostat."""
        nest_session = await self.ensure_authenticated()
        updated_payload = update_remote_comfort_sensing_payload(
            current_settings.raw_payload, target_sensor_id
        )
        request = encode_batch_update_state_request(
            thermostat_id,
            str(uuid4()),
            updated_payload,
        )

        try:
            await self._post_batch_update_state(nest_session.access_token, request)
        except NotAuthenticatedException:
            auth = await self.get_access_token()
            self.nest_session = await self.authenticate(auth.access_token)
            await self._post_batch_update_state(self.nest_session.access_token, request)

        return decode_remote_comfort_sensing_settings(updated_payload)

    async def _post_batch_update_state(
        self, nest_access_token: str, request_payload: bytes
    ) -> None:
        """Post a raw protobuf BatchUpdateState request."""
        async with self.session.post(
            f"{self.environment.grpc_host}{GRPC_BATCH_UPDATE_ENDPOINT}",
            data=request_payload,
            headers={
                "Authorization": f"Basic {nest_access_token}",
                "Content-Type": "application/x-protobuf",
                "User-Agent": USER_AGENT,
            },
            timeout=ClientTimeout(total=30),
        ) as response:
            if response.status == 401:
                raise NotAuthenticatedException(await response.text())
            if response.status != 200:
                snippet = (await response.content.read(256)).decode(
                    "utf-8", errors="ignore"
                )
                raise PynestException(
                    f"{response.status} error while updating thermostat - {snippet}"
                )

            response.close()
