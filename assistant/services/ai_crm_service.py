import json
import logging

from assistant.services.ai_service import AIService
from assistant.services.ai_crm_prompts import (
    contact_summary_prompt,
    lead_scoring_prompt,
    email_generator_prompt,
    follow_up_suggestions_prompt,
    crm_insights_prompt,
    daily_recommendations_prompt,
)
from assistant.services.exceptions import AIAssistantError

logger = logging.getLogger(__name__)


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class AICRMService:
    def __init__(self):
        self.ai = AIService()

    def _call(self, prompt):
        messages = [MockMessage('user', prompt)]
        return self.ai.generate_response(messages)

    def _parse_json(self, text):
        cleaned = text.strip()
        if cleaned.startswith('```') and '```' in cleaned[3:]:
            start = cleaned.find('\n') + 1
            end = cleaned.rfind('```')
            cleaned = cleaned[start:end].strip()
        return json.loads(cleaned)

    def contact_summary(self, contact):
        prompt = contact_summary_prompt(contact)
        return self._call(prompt)

    def lead_score(self, lead):
        prompt = lead_scoring_prompt(lead)
        raw = self._call(prompt)
        try:
            data = self._parse_json(raw)
            data['score'] = int(data.get('score', 0))
            return data
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error('Failed to parse lead score JSON: %s | Raw: %s', e, raw)
            return {
                'score': 0,
                'classification': 'Cold',
                'reasoning': 'Could not analyze this lead at this time.',
                'recommended_action': 'Review lead manually.',
            }

    def generate_email(self, contact, email_type):
        prompt = email_generator_prompt(contact, email_type)
        raw = self._call(prompt)
        try:
            return self._parse_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error('Failed to parse email JSON: %s | Raw: %s', e, raw)
            return {
                'subject': f'Regarding {contact.full_name}',
                'body': raw,
            }

    def follow_up_suggestions(self, lead):
        prompt = follow_up_suggestions_prompt(lead)
        raw = self._call(prompt)
        try:
            data = self._parse_json(raw)
            return data.get('suggestions', [])
        except (json.JSONDecodeError, ValueError) as e:
            logger.error('Failed to parse follow-up JSON: %s | Raw: %s', e, raw)
            return [
                {'action': 'Review lead details', 'timing': 'Today',
                 'reason': 'Manual review needed.'},
            ]

    def crm_insights(self, stats):
        prompt = crm_insights_prompt(stats)
        raw = self._call(prompt)
        try:
            data = self._parse_json(raw)
            return {
                'insights': data.get('insights', []),
                'recommendations': data.get('recommendations', []),
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error('Failed to parse insights JSON: %s | Raw: %s', e, raw)
            return {'insights': [], 'recommendations': []}

    def daily_recommendations(self, stats):
        prompt = daily_recommendations_prompt(stats)
        raw = self._call(prompt)
        try:
            data = self._parse_json(raw)
            return data.get('recommendations', [])
        except (json.JSONDecodeError, ValueError) as e:
            logger.error('Failed to parse daily recs JSON: %s | Raw: %s', e, raw)
            return []
