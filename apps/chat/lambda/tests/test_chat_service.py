import unittest
from unittest.mock import Mock

from chat_api.model_registry import MODEL_CAPABILITIES
from chat_api.providers.base import ProviderResponse
from chat_api.schemas import ChatRequest
from chat_api.services.chat_service import ChatService


class ChatServiceTests(unittest.TestCase):
    def test_handle_chat_delegates_to_orchestrator_and_maps_response(self) -> None:
        request = ChatRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4.1-mini",
        )
        capability = MODEL_CAPABILITIES[request.model]

        orchestrator = Mock()
        orchestrator.run.return_value = ProviderResponse(
            message="assistant reply",
            response_id="resp_123",
            input_tokens=11,
            output_tokens=22,
            duration_seconds=0.42,
        )

        service = ChatService(
            model_capabilities=MODEL_CAPABILITIES,
            orchestrator=orchestrator,
        )

        response = service.handle_chat(request)

        self.assertEqual(response.message, "assistant reply")
        self.assertEqual(response.response_id, "resp_123")
        self.assertEqual(response.input_tokens, 11)
        self.assertEqual(response.output_tokens, 22)
        self.assertEqual(response.duration_seconds, 0.42)

        orchestrator.run.assert_called_once()
        called_request, called_capability, called_message_count = orchestrator.run.call_args.args
        self.assertIs(called_request, request)
        self.assertIs(called_capability, capability)
        self.assertEqual(called_message_count, 1)


if __name__ == "__main__":
    unittest.main()
