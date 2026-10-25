"""Anbietereinrichtung ohne echte Konten, Netzwerkzugriffe oder Hardware."""

import asyncio
import copy
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

from rovo.cloud_http import CloudError, NoRedirect, request_json
from rovo.cloud_providers import PROVIDERS
from rovo.config import DEFAULT
from rovo.connections import Credentials
from rovo.core import Core
from rovo.dashboard import execute, projection
from rovo.mqtt_bridge import MQTTBridge


class ConnectionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data = Path(self.directory.name)
        self.core = Core(copy.deepcopy(DEFAULT), self.data)
        self.network = patch("rovo.spotify.request_json", new_callable=AsyncMock)
        self.spotify_http = self.network.start()
        self.llm_network = patch("rovo.llm.request_json", new_callable=AsyncMock)
        self.llm_http = self.llm_network.start()

    async def asyncTearDown(self):
        self.core.audio.spotify.active = False
        await self.core.close()
        self.network.stop()
        self.llm_network.stop()
        self.directory.cleanup()

    async def rpc(self, action, data=None, session="browser-a"):
        return await execute(self.core, {"action": action, "data": data or {}}, session)

    async def setup_llm(self, **changes):
        data = {
            "provider": "openai",
            "model": "test-model",
            "apiKey": "dummy-key",
            "allowCloud": True,
            "enabled": True,
        }
        data.update(changes)
        return await self.rpc("llm.save", data)

    def model_answer(self, emotion="CURIOUS"):
        return {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {"reply": "Testantwort", "emotion": emotion}
                            ),
                        }
                    ],
                }
            ],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }

    async def setup_spotify(self):
        result = await self.rpc(
            "spotify.save",
            {"clientId": "a" * 32, "redirectUri": "http://127.0.0.1:8888/callback"},
        )
        self.assertTrue(result["ok"])

    def seed_tokens(self, expired=False):
        self.core.credentials.save(
            "spotify",
            {
                "client_id": "a" * 32,
                "redirect_uri": "http://127.0.0.1:8888/callback",
                "access_token": "dummy-access",
                "refresh_token": "dummy-refresh",
                "device_id": "device-a",
                "expires_at": time.time() + (-1 if expired else 3600),
            },
        )

    async def callback(self):
        result = await self.rpc("spotify.login")
        query = parse_qs(urlsplit(result["connection_data"]["auth_url"]).query)
        return "http://127.0.0.1:8888/callback?" + urlencode(
            {"code": "dummy-code", "state": query["state"][0]}
        )

    def token_response(self, refresh=True):
        response = {
            "access_token": "dummy-new-access",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "user-modify-playback-state user-read-playback-state",
        }
        if refresh:
            response["refresh_token"] = "dummy-new-refresh"
        return response

    async def test_save_reload_no_network_or_secret_projection(self):
        self.assertTrue((await self.setup_llm())["ok"])
        self.seed_tokens()
        reloaded = Core(copy.deepcopy(DEFAULT), self.data)
        try:
            self.assertTrue(reloaded.llm.available())
            self.assertTrue(reloaded.audio.spotify.configured)
            self.assertFalse(reloaded.llm.public()["verified"])
            self.assertFalse(reloaded.audio.spotify.public()["verified"])
            public = json.dumps(projection(reloaded)) + json.dumps(reloaded.status())
            for private in ("dummy-key", "dummy-access", "dummy-refresh"):
                self.assertNotIn(private, public)
            self.assertTrue(reloaded.config["simulation"])
            self.assertTrue(reloaded.config["safe_mode"])
            self.assertEqual(reloaded.esp.commands, [])
            self.llm_http.assert_not_awaited()
            self.spotify_http.assert_not_awaited()
        finally:
            await reloaded.close()
        if os.name == "posix":
            self.assertEqual(self.core.credentials.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                self.core.credentials.path.parent.stat().st_mode & 0o777, 0o700
            )

    async def test_llm_consent_validation_and_key_retention(self):
        self.assertFalse((await self.setup_llm(allowCloud=False))["ok"])
        self.assertFalse(self.core.llm.available())
        for changes in (
            {"provider": "ollama"},
            {"model": "../other"},
            {"apiKey": "x\nInvalid"},
            {"enabled": "yes"},
            {"model": "x" * 121},
        ):
            self.assertFalse((await self.setup_llm(**changes))["ok"])
        self.assertTrue((await self.setup_llm())["ok"])
        self.assertTrue((await self.setup_llm(apiKey="", model="other-model"))["ok"])
        self.assertEqual(self.core.credentials.get("llm")["api_key"], "dummy-key")
        self.assertTrue((await self.setup_llm(apiKey="", enabled=False))["ok"])
        self.assertFalse(self.core.llm.available())
        self.llm_http.assert_not_awaited()

    async def test_llm_model_probe_contract_and_local_commands(self):
        await self.setup_llm()
        self.llm_http.return_value = self.model_answer()
        result = await self.rpc("llm.test")
        self.assertTrue(result["ok"])
        self.assertTrue(result["status"]["llm"]["verified"])
        args, kwargs = self.llm_http.call_args
        self.assertEqual(args, ("POST", "https://api.openai.com/v1/responses"))
        self.assertFalse(kwargs["data"]["store"])
        self.assertNotIn("tools", kwargs["data"])
        self.assertEqual(kwargs["data"]["text"]["format"]["type"], "json_schema")
        self.llm_http.reset_mock()
        for text in (
            "Nicht herunterfahren",
            "Keine Cloud-KI verwenden",
            "Was ist 2 plus 3?",
        ):
            await self.core.execute({"type": "text", "args": {"text": text}})
        self.llm_http.assert_not_awaited()
        self.assertFalse(self.core.llm.available())

    async def test_llm_bad_output_offline_and_privacy(self):
        await self.setup_llm()
        for response in (
            self.model_answer("MOVE"),
            {"status": "incomplete"},
            {"status": "completed", "output": []},
        ):
            self.llm_http.return_value = response
            self.assertFalse((await self.rpc("llm.test"))["ok"])
            self.assertIsNone(self.core.llm.verified_at)
        for status in (0, 401, 429, 503):
            self.llm_http.side_effect = CloudError(status)
            result = await self.rpc("llm.test")
            self.assertFalse(result["ok"])
            self.assertNotIn("dummy-key", str(result))
        self.core.privacy = True
        self.llm_http.reset_mock()
        self.assertFalse((await self.rpc("llm.test"))["ok"])
        self.llm_http.assert_not_awaited()

    async def test_forget_requires_confirmation_and_blocks_environment_fallback(self):
        await self.setup_llm()
        self.seed_tokens()
        for action in ("llm.forget", "spotify.disconnect"):
            self.assertFalse((await self.rpc(action))["ok"])
            self.assertFalse((await self.rpc(action, {"confirm": "yes"}))["ok"])
            self.assertTrue((await self.rpc(action, {"confirm": True}))["ok"])
        with patch.dict(
            "os.environ",
            {
                "ROVO_SPOTIFY_ACCESS_TOKEN": "dummy-env",
                "ROVO_SPOTIFY_DEVICE_ID": "device-env",
            },
        ):
            self.assertFalse(self.core.audio.spotify.configured)
            self.assertFalse((await self.rpc("spotify.test"))["ok"])
        saved = self.core.credentials.path.read_text(encoding="utf-8")
        self.assertNotIn("dummy-key", saved)
        self.assertNotIn("dummy-refresh", saved)
        self.assertFalse(self.core.llm.available())

    async def test_pkce_login_exchange_and_replay(self):
        await self.setup_spotify()
        callback = await self.callback()
        self.assertFalse(
            (
                await self.rpc(
                    "spotify.complete", {"callbackUrl": callback}, "browser-b"
                )
            )["ok"]
        )
        self.spotify_http.return_value = self.token_response()
        result = await self.rpc("spotify.complete", {"callbackUrl": callback})
        self.assertTrue(result["ok"])
        self.assertTrue(result["status"]["spotify"]["authorized"])
        self.assertFalse(result["status"]["spotify"]["configured"])
        sent = self.spotify_http.call_args.kwargs["data"]
        self.assertIn("code_verifier", sent)
        self.assertNotIn("client_secret", sent)
        self.assertFalse(
            (await self.rpc("spotify.complete", {"callbackUrl": callback}))["ok"]
        )
        self.assertNotIn("dummy-new-refresh", json.dumps(result))
        self.assertNotIn("dummy-code", json.dumps(result))

    async def test_oauth_state_expiry_cancel_and_bad_redirect(self):
        for uri in (
            "http://pi.local/callback",
            "http://localhost:8888/callback",
            "https://user:password@example.com/callback",
            "https://example.com/callback?token=x",
            "https://example.com:dummy-private/callback",
            "http://127.0.0.1:0/callback",
        ):
            result = await self.rpc(
                "spotify.save", {"clientId": "a" * 32, "redirectUri": uri}
            )
            self.assertFalse(result["ok"])
            self.assertNotIn("dummy-private", str(result))
        await self.setup_spotify()
        callback = await self.callback()
        for bad in (
            callback.replace("127.0.0.1", "127.0.0.2"),
            callback + "&state=another",
        ):
            self.assertFalse(
                (await self.rpc("spotify.complete", {"callbackUrl": bad}))["ok"]
            )
        self.core.audio.spotify.pending["deadline"] = 0
        self.assertFalse(
            (await self.rpc("spotify.complete", {"callbackUrl": callback}))["ok"]
        )
        for action in ("spotify.cancel", "motion.stop", "privacy.enable"):
            self.core.privacy = False
            callback = await self.callback()
            self.assertTrue((await self.rpc(action))["ok"])
            self.assertIsNone(self.core.audio.spotify.pending)
            self.assertFalse(
                (await self.rpc("spotify.complete", {"callbackUrl": callback}))["ok"]
            )
        self.spotify_http.assert_not_awaited()

    async def test_cancel_during_exchange_does_not_save_tokens(self):
        await self.setup_spotify()
        callback = await self.callback()
        started, finish = asyncio.Event(), asyncio.Event()

        async def exchange(*args, **kwargs):
            started.set()
            await finish.wait()
            return self.token_response()

        self.spotify_http.side_effect = exchange
        task = asyncio.create_task(
            self.rpc("spotify.complete", {"callbackUrl": callback})
        )
        await started.wait()
        self.assertTrue((await self.rpc("spotify.cancel"))["ok"])
        finish.set()
        self.assertFalse((await task)["ok"])
        self.assertNotIn("refresh_token", self.core.credentials.get("spotify"))

    async def test_refresh_rotation_and_restart_device_selection(self):
        self.seed_tokens(expired=True)
        self.spotify_http.side_effect = [
            self.token_response(),
            {
                "devices": [
                    {"id": "device-b", "name": "Testplayer", "type": "Speaker"},
                    {"id": "restricted", "is_restricted": True},
                ]
            },
        ]
        result = await self.rpc("spotify.devices")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["connection_data"]["devices"]), 1)
        self.assertEqual(
            self.core.credentials.get("spotify")["refresh_token"], "dummy-new-refresh"
        )
        self.assertTrue(
            (await self.rpc("spotify.select", {"deviceId": "device-b"}))["ok"]
        )
        self.assertEqual(Credentials(self.data).get("spotify")["device_id"], "device-b")
        self.spotify_http.side_effect = None
        self.spotify_http.return_value = {}
        await self.core.audio.spotify.pause(True)
        self.assertIn("device_id=device-b", self.spotify_http.call_args.args[1])

    async def test_refresh_keeps_nonrotated_token_and_one_401_retry(self):
        self.seed_tokens()
        self.spotify_http.side_effect = [
            CloudError(401),
            self.token_response(refresh=False),
            {"devices": []},
        ]
        self.assertTrue((await self.rpc("spotify.test"))["ok"])
        self.assertEqual(self.spotify_http.await_count, 3)
        self.assertEqual(
            self.core.credentials.get("spotify")["refresh_token"], "dummy-refresh"
        )
        self.spotify_http.reset_mock(side_effect=True)
        self.spotify_http.side_effect = CloudError(429)
        self.assertFalse((await self.rpc("spotify.test"))["ok"])
        self.assertEqual(self.spotify_http.await_count, 1)
        self.assertIsNone(self.core.audio.spotify.verified_at)

    async def test_revoked_refresh_requires_new_login(self):
        self.seed_tokens(expired=True)
        self.spotify_http.side_effect = CloudError(400, expired_grant=True)
        self.assertFalse((await self.rpc("spotify.test"))["ok"])
        self.assertFalse(self.core.audio.spotify.configured)
        self.assertNotIn("refresh_token", self.core.credentials.get("spotify"))
        self.assertFalse((await self.rpc("spotify.test"))["ok"])
        self.assertEqual(self.spotify_http.await_count, 1)

    async def test_stop_during_refresh_prevents_late_playback(self):
        self.seed_tokens(expired=True)

        async def stop(*args, **kwargs):
            await self.core.execute({"type": "stop", "args": {}})
            return self.token_response()

        self.spotify_http.side_effect = stop
        result = await self.core.execute(
            {"type": "music.spotify", "args": {"query": "Test"}}
        )
        self.assertFalse(result["ok"])
        self.assertEqual(self.spotify_http.await_count, 1)
        self.assertEqual(
            self.core.credentials.get("spotify")["access_token"], "dummy-access"
        )

    async def test_model_response_discarded_after_stop(self):
        await self.setup_llm()

        async def stop(*args, **kwargs):
            await self.core.execute({"type": "stop", "args": {}})
            return self.model_answer()

        self.llm_http.side_effect = stop
        self.assertFalse((await self.rpc("llm.test"))["ok"])
        self.assertIsNone(self.core.llm.verified_at)

    async def test_write_failure_preserves_active_configuration(self):
        await self.setup_llm()
        with patch(
            "rovo.connections.os.replace", side_effect=OSError("dummy-private-error")
        ):
            result = await self.setup_llm(apiKey="dummy-replacement")
        self.assertFalse(result["ok"])
        self.assertNotIn("dummy-private-error", str(result))
        self.assertEqual(self.core.credentials.get("llm")["api_key"], "dummy-key")
        self.assertFalse(list(self.core.credentials.path.parent.glob(".connections-*")))

    async def test_corrupt_private_file_fails_closed(self):
        await self.setup_llm()
        for content in (
            '{"llm": {"provider":"unknown"}, "spotify":{}}',
            '["llm", "spotify"]',
            "null",
            "{broken",
        ):
            self.core.credentials.path.write_text(content, encoding="utf-8")
            credentials = Credentials(self.data)
            self.assertIsNotNone(credentials.error)
            self.assertEqual(credentials.get("llm"), {})
            with self.assertRaises(ValueError):
                credentials.save("llm", {})

    async def test_mqtt_connection_roundtrip_contains_no_key(self):
        bridge = MQTTBridge(self.core, DEFAULT["mqtt"])
        bridge.client, bridge.connected = Mock(), True
        await bridge.handle(
            {
                "id": "connection-test",
                "boot_id": bridge.boot_id,
                "session": "browser-a",
                "issued_at": time.time(),
                "action": "llm.save",
                "data": {
                    "provider": "openai",
                    "model": "test-model",
                    "apiKey": "dummy-key",
                    "allowCloud": True,
                    "enabled": True,
                },
            }
        )
        payload = bridge.client.publish.call_args.args[1]
        self.assertTrue(json.loads(payload)["result"]["ok"])
        self.assertNotIn("dummy-key", payload)
        self.assertNotIn("dummy-key", str(bridge.seen))

    async def test_provider_keys_are_separate_and_reload_without_network(self):
        await self.setup_llm()
        self.assertFalse((await self.setup_llm(provider="anthropic", apiKey=""))["ok"])
        self.assertTrue(
            (
                await self.setup_llm(
                    provider="anthropic", apiKey="dummy-claude", model="claude-test"
                )
            )["ok"]
        )
        self.assertTrue((await self.setup_llm(apiKey=""))["ok"])
        self.assertEqual(self.core.credentials.get("llm")["api_key"], "dummy-key")
        public = json.dumps(projection(self.core))
        self.assertNotIn("dummy-claude", public)
        self.assertNotIn("dummy-key", public)
        await self.rpc("llm.forget", {"confirm": True})
        self.assertFalse(self.core.llm.available())
        self.assertTrue(
            (
                await self.setup_llm(
                    provider="anthropic", apiKey="", model="claude-test"
                )
            )["ok"]
        )
        reloaded = Core(copy.deepcopy(DEFAULT), self.data)
        try:
            self.assertTrue(reloaded.llm.available())
            self.assertEqual(reloaded.llm.public()["provider"], "anthropic")
            self.assertEqual(reloaded.credentials.get("llm")["api_key"], "dummy-claude")
        finally:
            await reloaded.close()
        self.llm_http.assert_not_awaited()

    async def test_six_provider_request_contracts_and_response_validation(self):
        content = json.dumps({"reply": "Testantwort", "emotion": "CURIOUS"})
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                self.assertTrue(
                    (
                        await self.setup_llm(
                            provider=provider, apiKey="dummy-" + provider
                        )
                    )["ok"]
                )
                if provider == "openai":
                    response = self.model_answer()
                elif provider == "anthropic":
                    response = {
                        "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": content}],
                    }
                elif provider == "google":
                    response = {
                        "candidates": [
                            {
                                "finishReason": "STOP",
                                "content": {"parts": [{"text": content}]},
                            }
                        ]
                    }
                else:
                    response = {
                        "choices": [
                            {"finish_reason": "stop", "message": {"content": content}}
                        ]
                    }
                self.llm_http.return_value = response
                result = await self.rpc("llm.test")
                self.assertTrue(result["ok"])
                args, kwargs = self.llm_http.call_args
                self.assertTrue(args[1].startswith(PROVIDERS[provider]["url"]))
                self.assertNotIn("tools", kwargs["data"])
                self.assertNotIn("dummy-" + provider, args[1])
                if provider == "anthropic":
                    self.assertEqual(kwargs["headers"]["x-api-key"], "dummy-anthropic")
                elif provider == "google":
                    self.assertEqual(
                        kwargs["headers"]["x-goog-api-key"], "dummy-google"
                    )
                else:
                    self.assertEqual(kwargs["token"], "dummy-" + provider)
                self.llm_http.return_value = {}
                self.assertFalse((await self.rpc("llm.test"))["ok"])
                self.assertIsNone(self.core.llm.verified_at)

    async def test_removed_model_management_actions_are_rejected(self):
        await self.setup_llm()
        before = self.core.credentials.get("llm")
        for action in ("llm.add_model", "llm.remove_model"):
            result = await self.rpc(
                action, {"provider": "openai", "model": "other-model"}
            )
            self.assertFalse(result["ok"])
        self.assertEqual(self.core.credentials.get("llm"), before)
        self.llm_http.assert_not_awaited()

    async def test_provider_model_catalogs_use_only_selected_key(self):
        for provider in PROVIDERS:
            await self.setup_llm(provider=provider, apiKey="dummy-" + provider)
        for provider in PROVIDERS:
            if provider == "google":
                self.llm_http.return_value = {
                    "models": [
                        {
                            "name": "models/model-a",
                            "supportedGenerationMethods": ["generateContent"],
                        },
                        {
                            "name": "models/embed",
                            "supportedGenerationMethods": ["embedContent"],
                        },
                    ]
                }
            else:
                self.llm_http.return_value = {
                    "data": [{"id": "model-a"}, {"id": "../invalid"}, {"id": "model-a"}]
                }
            result = await self.rpc("llm.models", {"provider": provider})
            self.assertTrue(result["ok"])
            self.assertEqual(result["connection_data"]["models"], ["model-a"])
            self.assertEqual(
                self.llm_http.call_args.args[:2], ("GET", PROVIDERS[provider]["models"])
            )
            self.assertNotIn("dummy-", json.dumps(result))
        self.assertEqual(self.core.llm.calls, 0)

    async def test_model_catalog_blocked_by_privacy_and_stop(self):
        await self.setup_llm()
        self.core.privacy = True
        self.assertFalse((await self.rpc("llm.models", {"provider": "openai"}))["ok"])
        self.llm_http.assert_not_awaited()
        self.core.privacy = False

        async def stop(*args, **kwargs):
            await self.core.execute({"type": "stop", "args": {}})
            return {"data": [{"id": "model-a"}]}

        self.llm_http.side_effect = stop
        self.assertFalse((await self.rpc("llm.models", {"provider": "openai"}))["ok"])

    async def test_model_list_can_store_first_key_without_activating_cloud(self):
        self.llm_http.return_value = {"data": [{"id": "first-model"}]}
        result = await self.rpc(
            "llm.models", {"provider": "anthropic", "apiKey": "dummy-first-key"}
        )
        self.assertTrue(result["ok"])
        self.assertFalse(self.core.llm.available())
        self.assertTrue(result["status"]["llm"]["profiles"]["anthropic"]["has_key"])
        self.assertNotIn("dummy-first-key", json.dumps(result))
        self.assertEqual(
            self.core.credentials.get("llm")["profiles"]["anthropic"]["api_key"],
            "dummy-first-key",
        )

    async def test_failed_model_list_retains_previous_key(self):
        await self.setup_llm()
        self.llm_http.side_effect = CloudError(401)
        self.assertFalse(
            (
                await self.rpc(
                    "llm.models", {"provider": "openai", "apiKey": "dummy-wrong-key"}
                )
            )["ok"]
        )
        self.assertEqual(self.core.credentials.get("llm")["api_key"], "dummy-key")

    async def test_legacy_single_provider_file_migrates_on_save(self):
        self.core.credentials.save(
            "llm",
            {
                "provider": "openai",
                "model": "legacy-model",
                "api_key": "dummy-legacy",
                "enabled": False,
                "allow_cloud": True,
            },
        )
        self.assertTrue((await self.setup_llm(apiKey=""))["ok"])
        self.assertEqual(
            self.core.credentials.get("llm")["profiles"]["openai"]["api_key"],
            "dummy-legacy",
        )

    async def test_legacy_model_lists_are_not_exposed(self):
        self.core.credentials.save(
            "llm",
            {
                "profiles": {
                    "openai": {
                        "api_key": None,
                        "model": None,
                        "models": ["legacy-model"],
                    }
                }
            },
        )
        self.assertNotIn("models", self.core.llm.public()["profiles"]["openai"])
        self.assertFalse(self.core.llm.available())

    async def test_provider_refusal_truncation_and_tools_are_rejected(self):
        bad_responses = {
            "anthropic": {"stop_reason": "max_tokens", "content": []},
            "google": {"candidates": [{"finishReason": "SAFETY"}]},
            "groq": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"tool_calls": [{"name": "move"}], "content": "{}"},
                    }
                ]
            },
            "mistral": {"choices": []},
            "openrouter": {"choices": [{"finish_reason": "length"}]},
        }
        for provider, response in bad_responses.items():
            await self.setup_llm(provider=provider, apiKey="dummy-key")
            self.llm_http.return_value = response
            self.assertFalse((await self.rpc("llm.test"))["ok"])
        self.assertEqual(self.core.esp.commands, [])

    async def test_privacy_pauses_music_but_blocks_new_playback(self):
        self.seed_tokens()
        self.core.audio.spotify.active = True
        self.core.audio.music_state = "PLAYING"
        self.spotify_http.return_value = {}
        result = await self.rpc("privacy.enable")
        self.assertTrue(result["ok"])
        self.assertIn("me/player/pause", self.spotify_http.call_args.args[1])
        self.assertFalse(self.core.audio.spotify.active)
        self.spotify_http.reset_mock()
        result = await self.rpc("music.spotify", {"query": "Test"})
        self.assertFalse(result["ok"])
        self.spotify_http.assert_not_awaited()

    async def test_failed_pause_preserves_unknown_player_state(self):
        self.seed_tokens()
        self.core.audio.spotify.active = True
        self.spotify_http.side_effect = CloudError()
        self.assertFalse((await self.rpc("music.stop"))["ok"])
        self.assertEqual(self.core.audio.music_state, "ERROR")
        self.assertTrue(self.core.audio.spotify.active)
        self.assertFalse(
            (await self.rpc("spotify.disconnect", {"confirm": True}))["ok"]
        )

    async def test_declined_login_is_consumed(self):
        await self.setup_spotify()
        callback = (await self.callback()).replace(
            "code=dummy-code", "error=access_denied"
        )
        self.assertFalse(
            (await self.rpc("spotify.complete", {"callbackUrl": callback}))["ok"]
        )
        self.assertIsNone(self.core.audio.spotify.pending)
        self.spotify_http.assert_not_awaited()

    async def test_saving_without_data_directory_fails_clearly(self):
        core = Core(copy.deepcopy(DEFAULT))
        try:
            result = await execute(
                core,
                {
                    "action": "llm.save",
                    "data": {
                        "provider": "openai",
                        "model": "test-model",
                        "apiKey": "dummy-key",
                        "allowCloud": True,
                        "enabled": True,
                    },
                },
                "browser-a",
            )
            self.assertFalse(result["ok"])
            self.assertIn("Datenordner", result["message"])
            self.assertFalse(core.llm.available())
        finally:
            await core.close()


class CloudHTTPTests(unittest.IsolatedAsyncioTestCase):
    async def test_error_body_and_redirect_never_expose_credentials(self):
        error = HTTPError(
            "https://example.invalid",
            401,
            "dummy-secret",
            {},
            io.BytesIO(b'{"error":"dummy-secret"}'),
        )
        with patch("rovo.cloud_http.build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaises(CloudError) as caught:
                await request_json(
                    "GET", "https://example.invalid", token="dummy-secret"
                )
            self.assertNotIn("dummy-secret", str(caught.exception))
        self.assertIsNone(
            NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://other.invalid"
            )
        )

    async def test_response_size_and_malformed_json_are_bounded(self):
        for body in (b"x" * 1_000_001, b"not-json", b"[]"):
            with patch("rovo.cloud_http.build_opener") as build:
                build.return_value.open.return_value.__enter__.return_value.read.return_value = body
                with self.assertRaises(CloudError):
                    await request_json("GET", "https://example.invalid")
