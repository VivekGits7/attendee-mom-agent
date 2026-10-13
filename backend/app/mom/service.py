import asyncio
from typing import Any, Optional

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)

from app.config import settings
from app.error import ExternalServiceException
from app.logger import get_logger
from app.mom.llm_output import MeetingMinutes
from app.prompts import get_system_prompt

logger = get_logger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 4, 8]

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _is_retryable_error(error: Exception) -> bool:
    return isinstance(
        error,
        (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError),
    )


async def _execute_with_retry(func, *args, operation_name: str, **kwargs) -> Any:
    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            if not _is_retryable_error(e):
                raise
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning(
                    f"{operation_name} failed, attempt {attempt + 1}/{MAX_RETRIES}: {type(e).__name__}. Retrying in {delay}s"
                )
                await asyncio.sleep(delay)
    raise last_error


async def generate_minutes(title: str, transcript_text: str) -> MeetingMinutes:
    user_message = get_system_prompt("mom", "user_template").format(
        title=title, transcript=transcript_text
    )
    try:
        response = await _execute_with_retry(
            get_openai_client().responses.parse,
            operation_name="MOM generation",
            model=settings.OPENAI_MOM_MODEL,
            instructions=get_system_prompt("mom"),
            input=[{"role": "user", "content": user_message}],
            text_format=MeetingMinutes,
            reasoning={"effort": settings.OPENAI_MOM_REASONING_EFFORT},
            max_output_tokens=settings.OPENAI_MOM_MAX_OUTPUT_TOKENS,
            prompt_cache_key="mom-v1",
        )
    except Exception as e:
        logger.error(f"MOM generation failed: {type(e).__name__}: {e}")
        raise ExternalServiceException("Could not generate the meeting minutes") from e

    if response.output_parsed is None:
        logger.error(
            f"MOM generation returned no parseable output: {(response.output_text or '')[:500]}"
        )
        raise ExternalServiceException("Could not generate the meeting minutes")
    return response.output_parsed
