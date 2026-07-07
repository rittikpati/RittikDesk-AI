import json
import logging
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


class AIService:
    _session = None

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY.strip() if settings.OPENROUTER_API_KEY else ''
        self.base_url = settings.OPENROUTER_BASE_URL
        self.timeout = settings.AI_TIMEOUT
        self.temperature = settings.AI_TEMPERATURE
        self.max_tokens = settings.AI_MAX_TOKENS

        if not self.api_key or "your-openrouter" in self.api_key.lower():
            logger.error("❌ OPENROUTER_API_KEY is missing or placeholder in .env!")

    @classmethod
    def _get_session(cls):
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    def _models(self):
        """Primary + Fallback models (no duplicates)"""
        primary = settings.OPENROUTER_MODEL
        models = [primary]
        raw = getattr(settings, 'OPENROUTER_FALLBACK_MODELS', [])
        if isinstance(raw, str):
            raw = [m.strip() for m in raw.split(',') if m.strip()]
        for m in raw:
            if m and m not in models:
                models.append(m)
        return models

    def generate_response(self, messages):
        """Non-streaming version (backup)"""
        if not self.api_key:
            return "AI service is not configured. Please contact admin."

        formatted = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for msg in messages:
            formatted.append({'role': msg.role, 'content': msg.content})

        for idx, model in enumerate(self._models()):
            if idx > 0:
                logger.info(f"🔄 Switching to fallback model: {model}")
                time.sleep(1.5)

            try:
                return self._call_model(model, formatted)
            except (RateLimitError, ServerError, AIAssistantError) as e:
                logger.warning(f"Model {model} failed: {type(e).__name__}")
                if idx == len(self._models()) - 1:
                    return "Sorry, all AI models are currently busy. Please try again later."
            except requests.exceptions.Timeout:
                logger.warning(f"Model {model} timed out")
                if idx == len(self._models()) - 1:
                    return "The AI service timed out. Please try again."
            except requests.exceptions.ConnectionError:
                logger.warning(f"Model {model} connection error")
                if idx == len(self._models()) - 1:
                    return "Could not connect to the AI service. Please check your network."
            except requests.exceptions.RequestException as e:
                logger.warning(f"Model {model} request failed: {e}")
                if idx == len(self._models()) - 1:
                    return "An error occurred while contacting the AI service. Please try again."
        return "An unexpected error occurred."

    def generate_stream(self, messages):
        """Streaming version with fallback support"""
        if not self.api_key:
            yield "AI service is not configured properly. Please add your OpenRouter API key in .env file."
            return

        formatted = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for msg in messages:
            formatted.append({'role': msg.role, 'content': msg.content})

        models = self._models()
        logger.info(f"🤖 Streaming request started with {len(models)} models. Primary: {models[0]}")

        for idx, model in enumerate(models):
            if idx > 0:
                logger.info(f"🔄 Switching to fallback model: {model}")
                time.sleep(2.0)   # Give some time before trying next model

            try:
                yield from self._call_model_stream(model, formatted)
                logger.info(f"✅ Streaming successful with model: {model}")
                return
            except (RateLimitError, ServerError) as e:
                logger.warning(f"⚠️ Model {model} failed (streaming): {e}")
            except (AuthenticationError, ModelNotFoundError) as e:
                logger.error(f"❌ Critical error with {model}: {e}")
                yield "Authentication or model error occurred. Please check API key."
                return
            except AIAssistantError as e:
                logger.warning(f"Model {model} rejected: {e}")
                if idx == len(models) - 1:
                    yield "Sorry, I am unable to respond right now. All models are busy."
                    return
            except requests.exceptions.Timeout:
                logger.warning(f"Model {model} timed out (streaming)")
                if idx == len(models) - 1:
                    yield "The AI service timed out. Please try again."
                    return
            except requests.exceptions.ConnectionError:
                logger.warning(f"Model {model} connection error (streaming)")
                if idx == len(models) - 1:
                    yield "Could not connect to the AI service. Please check your network."
                    return
            except requests.exceptions.RequestException as e:
                logger.warning(f"Model {model} request failed (streaming): {e}")
                if idx == len(models) - 1:
                    yield "An error occurred while contacting the AI service. Please try again."
                    return

        yield "Sorry, all AI models are currently unavailable. Please try again in a few minutes."

    def _call_model(self, model, formatted_messages):
        """Normal (non-stream) call"""
        url = f'{self.base_url}/chat/completions'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'http://localhost:8000',
            'X-Title': 'RittikDesk',
        }

        payload = {
            'model': model,
            'messages': formatted_messages,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }

        response = self._get_session().post(url, headers=headers, json=payload, timeout=self.timeout)

        if response.status_code != 200:
            self._handle_error(response, model)

        return response.json()['choices'][0]['message']['content']

    def _call_model_stream(self, model, formatted_messages):
        """Streaming call"""
        url = f'{self.base_url}/chat/completions'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'http://localhost:8000',
            'X-Title': 'RittikDesk',
        }

        payload = {
            'model': model,
            'messages': formatted_messages,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'stream': True,
        }

        response = self._get_session().post(
            url, headers=headers, json=payload, stream=True, timeout=self.timeout
        )

        if response.status_code != 200:
            self._handle_error(response, model)

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

    def _handle_error(self, response, model):
        """Centralized error handler"""
        try:
            body = response.json()
            error_msg = body.get('error', {}).get('message', response.text[:150])
        except Exception:
            error_msg = response.text[:150]

        logger.error(f"OpenRouter Error | Model: {model} | Status: {response.status_code} | Message: {error_msg}")

        if response.status_code == 401:
            raise AuthenticationError(f"Invalid API Key: {error_msg}")
        if response.status_code == 404:
            raise ModelNotFoundError(f"Model not found: {error_msg}")
        if response.status_code == 429:
            raise RateLimitError(f"Rate limit exceeded: {error_msg}")
        if response.status_code >= 500:
            raise ServerError(f"Server error: {error_msg}")

        raise AIAssistantError(f"HTTP {response.status_code}: {error_msg}")