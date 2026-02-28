import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

import app as app_module
from chat_api.errors import BadRequestError
from chat_api.schemas import ChatResponse


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module.get_chat_service.cache_clear()

    def test_health_endpoint(self) -> None:
        with TestClient(app_module.app) as client:
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_models_endpoint_returns_capability_fields(self) -> None:
        with TestClient(app_module.app) as client:
            response = client.get("/api/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload), 1)

        first = payload[0]
        self.assertIn("id", first)
        self.assertIn("supportsTemperature", first)
        self.assertIn("supportsReasoningEffort", first)
        self.assertIn("reasoningEffortOptions", first)
        self.assertIn("defaultReasoningEffort", first)
        self.assertIn("supportsWebSearch", first)
        self.assertIn("supportsPreviousResponse", first)

    def test_chat_endpoint_success_response_shape(self) -> None:
        chat_service = Mock()
        chat_service.handle_chat.return_value = ChatResponse(
            message="hello",
            response_id="resp_success",
            input_tokens=10,
            output_tokens=20,
            duration_seconds=0.35,
        )

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(app_module, "ensure_langsmith_configured", return_value=None)
            )
            flush_mock = stack.enter_context(
                patch.object(app_module, "flush_langsmith_traces", return_value=None)
            )
            stack.enter_context(
                patch.object(app_module, "get_chat_service", return_value=chat_service)
            )
            with TestClient(app_module.app) as client:
                response = client.post(
                    "/api/chat",
                    json={
                        "model": "gpt-4.1-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["message"], "hello")
        self.assertEqual(payload["responseId"], "resp_success")
        self.assertEqual(payload["inputTokens"], 10)
        self.assertEqual(payload["outputTokens"], 20)
        self.assertEqual(payload["durationSeconds"], 0.35)
        self.assertEqual(flush_mock.call_count, 1)

    def test_chat_endpoint_invalid_model_returns_422(self) -> None:
        with TestClient(app_module.app) as client:
            response = client.post(
                "/api/chat",
                json={
                    "model": "invalid-model",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )

        self.assertEqual(response.status_code, 422)

    def test_chat_endpoint_bad_request_error_maps_to_400(self) -> None:
        chat_service = Mock()
        chat_service.handle_chat.side_effect = BadRequestError("invalid attachment")

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(app_module, "ensure_langsmith_configured", return_value=None)
            )
            flush_mock = stack.enter_context(
                patch.object(app_module, "flush_langsmith_traces", return_value=None)
            )
            stack.enter_context(
                patch.object(app_module, "get_chat_service", return_value=chat_service)
            )
            with TestClient(app_module.app) as client:
                response = client.post(
                    "/api/chat",
                    json={
                        "model": "gpt-4.1-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "invalid attachment")
        self.assertEqual(flush_mock.call_count, 1)

    def test_chat_endpoint_unexpected_error_maps_to_502(self) -> None:
        chat_service = Mock()
        chat_service.handle_chat.side_effect = RuntimeError("provider down")

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(app_module, "ensure_langsmith_configured", return_value=None)
            )
            flush_mock = stack.enter_context(
                patch.object(app_module, "flush_langsmith_traces", return_value=None)
            )
            stack.enter_context(
                patch.object(app_module, "get_chat_service", return_value=chat_service)
            )
            with TestClient(app_module.app) as client:
                response = client.post(
                    "/api/chat",
                    json={
                        "model": "gpt-4.1-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "provider down")
        self.assertEqual(flush_mock.call_count, 1)


if __name__ == "__main__":
    unittest.main()
