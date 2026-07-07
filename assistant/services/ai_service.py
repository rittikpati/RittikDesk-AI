import json
import logging

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
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.timeout = settings.AI_TIMEOUT
        self.temperature = settings.AI_TEMPERATURE
        self.max_tokens = settings.AI_MAX_TOKENS

    @classmethod
    def _get_session(cls):
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    def _models(self):
        primary = settings.OPENROUTER_MODEL
        seen = [primary]
        raw = settings.OPENROUTER_FALLBACK_MODELS
        if raw:
            for model in raw.split(','):
                model = model.strip()
                if model and model not in seen:
                    seen.append(model)
        return seen

    def generate_response(self, messages):
        if not self.api_key:
            raise AuthenticationError('API key is not configured. Please set OPENROUTER_API_KEY.')

        formatted = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for msg in messages:
            formatted.append({'role': msg.role, 'content': msg.content})

        models = self._models()
        last_exception = None

        for idx, model in enumerate(models):
            if idx > 0:
                logger.info('Switching to fallback model: %s', model)

            try:
                result = self._call_model(model, formatted)
                logger.info('Successful response from model: %s', model)
                return result
            except RateLimitError as e:
                logger.warning('Model %s rate-limited: %s', model, e)
                last_exception = e
            except ServerError as e:
                logger.warning('Model %s server error: %s', model, e)
                last_exception = e
            except ModelNotFoundError as e:
                logger.warning('Model %s not found or invalid: %s', model, e)
                last_exception = e
            except AIAssistantError as e:
                if '400' in str(e) or 'invalid' in str(e).lower():
                    logger.warning('Model %s rejected (HTTP 400): %s', model, e)
                    last_exception = e
                    continue
                raise

        raise RateLimitError(
            'All free AI providers are currently busy. Please try again in a few minutes.'
        )

    def _call_model(self, model, formatted_messages):
        url = f'{self.base_url}/chat/completions'

        masked_key = self.api_key[:8] + '...' if len(self.api_key) > 8 else '***'
        logger.info('OpenRouter request URL: %s', url)
        logger.info('OpenRouter model: %s', model)
        logger.info('OpenRouter Authorization: Bearer %s', masked_key)

        session = self._get_session()
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://rittikdesk.ai',
        }

        payload = {
            'model': model,
            'messages': formatted_messages,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
        }

        try:
            response = session.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise TimeoutError('The AI service took too long to respond. Please try again.')
        except requests.exceptions.ConnectionError:
            raise NetworkError('Could not connect to the AI service. Please check your network.')
        except requests.exceptions.RequestException as e:
            logger.exception('AI request failed')
            raise NetworkError(f'Network error occurred: {str(e)}')

        logger.info('OpenRouter HTTP %s', response.status_code)

        body = None
        raw_text = response.text
        try:
            body = response.json()
        except Exception:
            pass

        if body and isinstance(body, dict):
            logger.info('OpenRouter response body (JSON):\n%s', json.dumps(body, indent=2))
        else:
            logger.info('OpenRouter response body (raw):\n%s', raw_text)

        if response.status_code != 200:
            logger.error('OpenRouter error (HTTP %s) full response:\n%s', response.status_code, json.dumps(body, indent=2) if body and isinstance(body, dict) else raw_text)

        def error_msg(fallback):
            if body and isinstance(body, dict):
                return body.get('error', {}).get('message', fallback)
            return fallback

        if response.status_code == 401:
            raise AuthenticationError(f'OpenRouter (HTTP 401): {error_msg("Invalid API key.")}')
        if response.status_code == 403:
            raise AuthenticationError(f'OpenRouter (HTTP 403): {error_msg("Access denied.")}')
        if response.status_code == 404:
            raise ModelNotFoundError(f'OpenRouter (HTTP 404): {error_msg("Model not found.")}')
        if response.status_code == 429:
            raise RateLimitError(f'OpenRouter (HTTP 429): {error_msg("API rate limit exceeded.")}')
        if response.status_code >= 500:
            raise ServerError(f'OpenRouter (HTTP {response.status_code}): {error_msg("Server error.")}')

        if response.status_code != 200:
            raise AIAssistantError(f'OpenRouter (HTTP {response.status_code}): {raw_text[:1000]}')

        return body['choices'][0]['message']['content']
