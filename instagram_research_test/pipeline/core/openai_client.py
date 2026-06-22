"""Core: обёртка над OpenAI API с retry."""

import time
import logging
from pipeline.core.config import get_openai_key

logger = logging.getLogger(__name__)


def get_client():
    """Возвращает инициализированный OpenAI клиент."""
    from openai import OpenAI
    return OpenAI(api_key=get_openai_key())


def chat(messages: list, model: str = "gpt-4o",
         max_tokens: int = 1000, retries: int = 3) -> str:
    """
    Отправляет сообщения в OpenAI, возвращает текст ответа.
    Retry с exponential backoff на RateLimitError и APIError.
    """
    from openai import RateLimitError, APIError
    client = get_client()

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except (RateLimitError, APIError) as e:
            if attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning(f"OpenAI attempt {attempt+1}/{retries} failed: {e}. Retry in {wait}s")
                time.sleep(wait)
            else:
                raise


def vision(images_b64: list, prompt: str, model: str = "gpt-4o",
           max_tokens: int = 1000) -> str:
    """
    Vision-запрос: images_b64 = [{"b64": "...", "detail": "high"}]
    Возвращает текст ответа.
    """
    content = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img['b64']}",
                "detail": img.get("detail", "high"),
            }
        })
    return chat([{"role": "user", "content": content}], model=model, max_tokens=max_tokens)
