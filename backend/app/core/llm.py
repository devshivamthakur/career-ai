from typing import Any

from app.core.config import settings
import botocore.session

def build_chat_model(streaming: bool = False, callbacks: list | None = None, temperature: float = 0) -> Any:
    """Instantiate the configured chat model for the current LLM provider."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "aws":
        from langchain_aws import ChatBedrockConverse
        

        return ChatBedrockConverse(
            model=settings.FAST_MODEL_NAME,
            streaming=False,  # AWS Bedrock does not support streaming responses
            temperature=temperature,
            callbacks=callbacks or [],
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        model=settings.FAST_MODEL_NAME,
        temperature=temperature,
        streaming=streaming,
        callbacks=callbacks or [],
    )
