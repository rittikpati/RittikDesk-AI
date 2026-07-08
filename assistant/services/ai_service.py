import json
import logging
import random
import time

import requests
from django.conf import settings

from .exceptions import (
    AIAssistantError,
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ModelNotFoundError,
    ServerError,
    NetworkError,
)
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_CONTEXT_TOKENS = 8000
TOKEN_ESTIMATE_FACTOR = 4  # rough: 1 token ≈ 4 chars
SYSTEM_PROMPT_TOKENS = len(SYSTEM_PROMPT) // TOKEN_ESTIMATE_FACTOR + 200


USER_FRIENDLY_ERRORS = {
    AuthenticationError: (
        "There's an authentication issue with the AI service. "
        "Please contact your administrator to check the API configuration."
    ),
    RateLimitError: (
        "The AI service is temporarily busy due to high demand. "
        "Please wait a moment and try again."
    ),
    TimeoutError: (
        "The AI service took too long to respond. "
        "Please try again — sometimes a retry is all it needs."
    ),
    ModelNotFoundError: (
        "The requested AI model is not available right now. "
        "A fallback model will be used automatically."
    ),
    ServerError: (
        "The AI service is temporarily unavailable. "
        "Please try again in a few moments."
    ),
    NetworkError: (
        "Could not reach the AI service. "
        "Please check your internet connection and try again."
    ),
}

DEFAULT_ERROR = (
    "I'm having trouble connecting to the AI service right now. "
    "Please try again in a moment."
)

API_KEY_MISSING_ERROR = (
    "The AI assistant needs an API key to work. "
    "Please ask your administrator to add the OpenRouter API key to the .env file."
)


def _user_message(exc):
    for exc_type, msg in USER_FRIENDLY_ERRORS.items():
        if isinstance(exc, exc_type):
            return msg
    return DEFAULT_ERROR


def _is_placeholder_key(api_key):
    if not api_key:
        return True
    lowered = api_key.lower()
    return any(word in lowered for word in ['your-openrouter', 'placeholder', 'sk-or-v1-'])


def _truncate_context(messages, max_chars=MAX_CONTEXT_TOKENS * TOKEN_ESTIMATE_FACTOR):
    """Trim oldest messages to stay within a rough token budget.

    Always keeps system-prompt messages and the most recent conversation.
    """
    system_msgs = [m for m in messages if m.get('role') == 'system']
    history_msgs = [m for m in messages if m.get('role') != 'system']

    system_chars = sum(len(m.get('content', '')) + 50 for m in system_msgs)
    total_chars = system_chars + sum(
        len(m.get('content', '')) + 50 for m in history_msgs
    )
    if total_chars <= max_chars:
        return messages

    budget = max_chars - system_chars
    trimmed = []
    for m in reversed(history_msgs):
        cost = len(m.get('content', '')) + 50
        if budget - cost >= 0:
            trimmed.insert(0, m)
            budget -= cost

    return system_msgs + trimmed


_session = None


def _get_session():
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _build_headers(api_key):
    return {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'http://localhost:8000',
        'X-Title': 'RittikDesk',
    }


def _build_payload(model, messages, stream=False):
    return {
        'model': model,
        'messages': messages,
        'temperature': settings.AI_TEMPERATURE,
        'max_tokens': settings.AI_MAX_TOKENS,
        'stream': stream,
    }


def _models():
    """Primary + fallback models (deduplicated)."""
    primary = settings.OPENROUTER_MODEL
    result = [primary]
    raw = getattr(settings, 'OPENROUTER_FALLBACK_MODELS', [])
    if isinstance(raw, str):
        raw = [m.strip() for m in raw.split(',') if m.strip()]
    for m in raw:
        if m and m not in result:
            result.append(m)
    return result


def _handle_error_response(response, model):
    """Centralized error handler — raises typed exceptions."""
    try:
        body = response.json()
        error_msg = body.get('error', {}).get('message', response.text[:150])
    except Exception:
        error_msg = response.text[:150]

    logger.error("OpenRouter Error | Model: %s | Status: %s | Message: %s",
                 model, response.status_code, error_msg)

    if response.status_code == 401:
        raise AuthenticationError(error_msg)
    if response.status_code == 404:
        raise ModelNotFoundError(error_msg)
    if response.status_code == 429:
        raise RateLimitError(error_msg)
    if response.status_code >= 500:
        raise ServerError(error_msg)

    raise AIAssistantError(f"HTTP {response.status_code}: {error_msg}")


def _call_model(api_key, model, formatted_messages):
    """Non-streaming call to a single model."""
    session = _get_session()
    response = session.post(
        f'{settings.OPENROUTER_BASE_URL}/chat/completions',
        headers=_build_headers(api_key),
        json=_build_payload(model, formatted_messages),
        timeout=settings.AI_TIMEOUT,
    )
    if response.status_code != 200:
        _handle_error_response(response, model)
    return response.json()['choices'][0]['message']['content']


def _call_model_stream(api_key, model, formatted_messages):
    """Streaming call to a single model. Yields content tokens."""
    session = _get_session()
    response = session.post(
        f'{settings.OPENROUTER_BASE_URL}/chat/completions',
        headers=_build_headers(api_key),
        json=_build_payload(model, formatted_messages, stream=True),
        stream=True,
        timeout=settings.AI_TIMEOUT,
    )
    if response.status_code != 200:
        _handle_error_response(response, model)

    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode('utf-8')
        if line.startswith('data: '):
            data = line[6:].strip()
            if data == '[DONE]':
                break
            try:
                chunk = json.loads(data)
                content = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue


class AIService:
    """High-level AI service with fallback, retry, and context trimming."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY.strip() if settings.OPENROUTER_API_KEY else ''
        if _is_placeholder_key(self.api_key):
            logger.error("OPENROUTER_API_KEY is missing or a placeholder in .env")

    def _format_messages(self, messages, crm_context=None):
        """Convert DB message objects to API format with context trimming."""
        formatted = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        if crm_context:
            formatted.append({'role': 'system', 'content': crm_context})
        for msg in messages:
            formatted.append({'role': msg.role, 'content': msg.content})
        return _truncate_context(formatted)

    def generate_response(self, messages, crm_context=None):
        """Non-streaming response with automatic fallback."""
        if not self.api_key:
            return API_KEY_MISSING_ERROR

        formatted = self._format_messages(messages, crm_context)

        for idx, model in enumerate(_models()):
            if idx > 0:
                delay = 1.0 + random.random()
                logger.info("Falling back to model: %s (delay=%.1fs)", model, delay)
                time.sleep(delay)

            try:
                return _call_model(self.api_key, model, formatted)
            except (RateLimitError, ServerError) as e:
                logger.warning("Model %s failed: %s", model, e)
                if idx == len(_models()) - 1:
                    return _user_message(e)
            except requests.exceptions.Timeout:
                logger.warning("Model %s timed out", model)
                if idx == len(_models()) - 1:
                    return _user_message(TimeoutError("timeout"))
            except requests.exceptions.ConnectionError:
                logger.warning("Model %s connection error", model)
                if idx == len(_models()) - 1:
                    return _user_message(NetworkError("connection"))
            except requests.exceptions.RequestException as e:
                logger.warning("Model %s request failed: %s", model, e)
                if idx == len(_models()) - 1:
                    return DEFAULT_ERROR
        return DEFAULT_ERROR

    def generate_stream(self, messages, crm_context=None):
        """Streaming response with automatic fallback. Yields tokens."""
        if not self.api_key:
            yield API_KEY_MISSING_ERROR
            return

        formatted = self._format_messages(messages, crm_context)
        models = _models()
        logger.info("Streaming with %d models. Primary: %s", len(models), models[0])

        for idx, model in enumerate(models):
            if idx > 0:
                delay = 1.5 + random.random()
                logger.info("Fallback stream model: %s (delay=%.1fs)", model, delay)
                time.sleep(delay)

            try:
                yield from _call_model_stream(self.api_key, model, formatted)
                logger.info("Streaming successful with model: %s", model)
                return
            except (RateLimitError, ServerError) as e:
                logger.warning("Stream model %s failed: %s", model, e)
                if idx == len(models) - 1:
                    yield _user_message(e)
                    return
            except (AuthenticationError, ModelNotFoundError) as e:
                logger.error("Critical error with %s: %s", model, e)
                yield _user_message(e)
                return
            except AIAssistantError as e:
                logger.warning("Model %s rejected: %s", model, e)
                if idx == len(models) - 1:
                    yield _user_message(e)
                    return
            except requests.exceptions.Timeout:
                logger.warning("Model %s stream timed out", model)
                if idx == len(models) - 1:
                    yield _user_message(TimeoutError("timeout"))
                    return
            except requests.exceptions.ConnectionError:
                logger.warning("Model %s connection error", model)
                if idx == len(models) - 1:
                    yield _user_message(NetworkError("connection"))
                    return
            except requests.exceptions.RequestException as e:
                logger.warning("Model %s stream failed: %s", model, e)
                if idx == len(models) - 1:
                    yield DEFAULT_ERROR
                    return

        yield DEFAULT_ERROR
