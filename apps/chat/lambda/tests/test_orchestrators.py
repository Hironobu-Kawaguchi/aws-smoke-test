import unittest

from chat_api.model_registry import MODEL_CAPABILITIES
from chat_api.orchestration.direct import DirectChatOrchestrator
from chat_api.orchestration.langgraph_flow import LangGraphChatOrchestrator
from chat_api.providers.base import ProviderResponse
from chat_api.schemas import ChatRequest


class StubProvider:
    def __init__(self, response: ProviderResponse) -> None:
        self._response = response
        self.calls: list[tuple[ChatRequest, object, int]] = []

    def invoke(
        self, request: ChatRequest, capability: object, message_count: int
    ) -> ProviderResponse:
        self.calls.append((request, capability, message_count))
        return self._response


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = ChatRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="gpt-4.1-mini",
        )
        self.capability = MODEL_CAPABILITIES[self.request.model]
        self.expected_response = ProviderResponse(
            message="ok",
            response_id="resp_1",
            input_tokens=5,
            output_tokens=7,
            duration_seconds=0.1,
        )

    def test_direct_orchestrator_routes_to_provider(self) -> None:
        provider = StubProvider(self.expected_response)
        orchestrator = DirectChatOrchestrator(providers={"openai": provider})

        response = orchestrator.run(self.request, self.capability, message_count=1)

        self.assertEqual(response, self.expected_response)
        self.assertEqual(len(provider.calls), 1)
        called_request, called_capability, called_count = provider.calls[0]
        self.assertIs(called_request, self.request)
        self.assertIs(called_capability, self.capability)
        self.assertEqual(called_count, 1)

    def test_direct_orchestrator_raises_for_missing_provider(self) -> None:
        orchestrator = DirectChatOrchestrator(providers={})

        with self.assertRaisesRegex(RuntimeError, "Unsupported provider: openai"):
            orchestrator.run(self.request, self.capability, message_count=1)

    def test_langgraph_orchestrator_routes_to_provider(self) -> None:
        provider = StubProvider(self.expected_response)
        orchestrator = LangGraphChatOrchestrator(providers={"openai": provider})

        response = orchestrator.run(self.request, self.capability, message_count=1)

        self.assertEqual(response, self.expected_response)
        self.assertEqual(len(provider.calls), 1)
        called_request, called_capability, called_count = provider.calls[0]
        self.assertIs(called_request, self.request)
        self.assertIs(called_capability, self.capability)
        self.assertEqual(called_count, 1)

    def test_langgraph_orchestrator_raises_for_missing_provider(self) -> None:
        orchestrator = LangGraphChatOrchestrator(providers={})

        with self.assertRaisesRegex(RuntimeError, "Unsupported provider: openai"):
            orchestrator.run(self.request, self.capability, message_count=1)


if __name__ == "__main__":
    unittest.main()
