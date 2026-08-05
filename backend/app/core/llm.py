from typing import Any

from app.core.config import settings


def build_chat_model(
    streaming: bool = False,
    callbacks: list | None = None,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> Any:
    """Instantiate the configured chat model for the current LLM provider.

    All providers are configured with streaming enabled when requested.
    Token-by-token streaming is critical for real-time SSE output.
    """
    provider = settings.LLM_PROVIDER.lower()
    max_tokens = max_tokens or settings.FAST_MODEL_MAX_TOKENS

    if provider == "aws":
        from langchain_aws import ChatBedrockConverse

        return ChatBedrockConverse(
            model=settings.FAST_MODEL_NAME,
            streaming=streaming,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=callbacks or [],
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        model=settings.FAST_MODEL_NAME,
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=streaming,
        callbacks=callbacks or [],
        # Bound retries & request timeouts so slow/failed LLM calls fail fast
        # instead of hanging workers indefinitely.
        max_retries=2,
        request_timeout=60,
    )

