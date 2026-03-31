"""GitHub Models API provider — free LLM via GITHUB_TOKEN."""

import os

import httpx

from cifi.config import Config


class GitHubModelsProvider:
    """Free LLM via GitHub Models API. Uses GITHUB_TOKEN. Zero config."""

    BASE_URL = "https://models.github.ai/inference"
    API_VERSION = "2026-03-10"

    def __init__(self, config: Config) -> None:
        self.model = config.default_model
        api_key = config.llm_api_key or os.environ.get("GITHUB_TOKEN", "")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
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
