import os

from deepeval.models.base_model import DeepEvalBaseLLM


class AgoraGatewayLLM(DeepEvalBaseLLM):
    """
    A custom DeepEval LLM that routes all evaluation generation requests
    through the internal Agora LLM Gateway via bos://capability/llm-gateway.
    """

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self.model_name = model_name
        self.gateway_url = os.environ.get(
            "AGORA_HTTP_PORT", f"http://localhost:{os.environ.get('ONTODERIVE_WEB_PORT', '8080')}"
        )

    def load_model(self) -> "AgoraGatewayLLM":
        return self

    def generate(self, prompt: str) -> str:
        # In a real scenario, this would call the bos:// capability via httpx
        # to the Agora gateway. For now, it's a mocked interface for VibeOps.
        return f"Mocked Agora Gateway Evaluation for: {prompt[:20]}..."

    async def a_generate(self, prompt: str) -> str:
        # Async generation matching Agora async proxy
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model_name
