"""GitHub Models API provider — free LLM via GITHUB_TOKEN."""

import httpx

from cifi.config import Config


class GitHubModelsProvider:
    """Free LLM via GitHub Models API. Uses GITHUB_TOKEN. Zero config."""

    BASE_URL = "https://models.github.ai/inference"
    API_VERSION = "2026-03-10"
    DEFAULT_MODEL = "openai/gpt-4o-mini"

    def __init__(self, config: Config) -> None:
        if not config.llm_api_key:
            raise ValueError(
                "GitHubModelsProvider requires an API key. "
                "Set CIFI_LLM_API_KEY or GITHUB_TOKEN."
            )
        self.model = config.llm_model or self.DEFAULT_MODEL
        self._headers = {
            "Authorization": f"Bearer {config.llm_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": self.API_VERSION,
        }

    async def analyze(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
