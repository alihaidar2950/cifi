"""LLM Analyzer — orchestrates the analysis pipeline."""

import asyncio
import json
import logging

from cifi.config import Config
from cifi.llm import create_provider
from cifi.prompts import build_prompt
from cifi.schemas import AnalysisResult, ProcessedContext

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Raised when LLM analysis fails after all retries."""


async def analyze(
    context: ProcessedContext,
    config: Config | None = None,
) -> AnalysisResult:
    """Analyze failure using multi-provider LLM.

    Builds prompt, calls provider, validates response against Pydantic schema.
    Retries with exponential backoff on validation errors or transient failures.
    """
    config = config or Config.from_env()
    provider = create_provider(config)
    prompt = build_prompt(context)

    last_error: Exception | None = None

    for attempt in range(config.max_retries):
        try:
            raw = await provider.analyze(prompt)

            # Strip markdown code fences if the LLM wraps the JSON
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            result = AnalysisResult.model_validate_json(cleaned)
            logger.info("Analysis succeeded on attempt %d", attempt + 1)
            return result

        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning("Validation failed on attempt %d: %s", attempt + 1, exc)
            if attempt < config.max_retries - 1:
                await asyncio.sleep(2**attempt)

        except Exception as exc:
            last_error = exc
            logger.warning("LLM call failed on attempt %d: %s", attempt + 1, exc)
            if attempt < config.max_retries - 1:
                await asyncio.sleep(2**attempt)

    raise AnalysisError(f"Analysis failed after {config.max_retries} attempts: {last_error}")
