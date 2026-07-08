import re

from django.conf import settings


COMMON_TYPOS = {
    'modi joi': 'Narendra Modi, the Prime Minister of India',
    'modi': 'Narendra Modi, the Prime Minister of India',
    'trumph': 'Donald Trump, former President of the United States',
    'obama': 'Barack Obama, former President of the United States',
    'biden': 'Joe Biden, former President of the United States',
    'putin': 'Vladimir Putin, President of Russia',
    'python': 'the Python programming language',
    'django': 'the Django web framework',
    'js': 'JavaScript',
    'javascript': 'JavaScript',
    'ts': 'TypeScript',
    'typescript': 'TypeScript',
    'gpt': 'GPT (Generative Pre-trained Transformer)',
    'llm': 'LLM (Large Language Model)',
    'ai': 'Artificial Intelligence',
    'ml': 'Machine Learning',
    'dl': 'Deep Learning',
    'nlp': 'Natural Language Processing',
    'db': 'database',
    'sql': 'Structured Query Language',
    'html': 'HTML (HyperText Markup Language)',
    'css': 'CSS (Cascading Style Sheets)',
    'api': 'API (Application Programming Interface)',
    'rest': 'REST (Representational State Transfer)',
    'json': 'JavaScript Object Notation',
    'crm': 'CRM (Customer Relationship Management)',
    'ui': 'User Interface',
    'ux': 'User Experience',
    'devops': 'DevOps practices',
    'git': 'Git version control',
    'agile': 'Agile methodology',
}


def infer_intent(text):
    """Try to infer user intent from potentially garbled input.

    Returns an expansion string if a known typo/shorthand is found, else None.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        return None

    exact = COMMON_TYPOS.get(cleaned)
    if exact:
        return exact

    for key, expansion in COMMON_TYPOS.items():
        if key in cleaned:
            return expansion

    return None


def sanitize_message(content):
    return content.strip()[:10000]


def truncate_title(text, length=50):
    cleaned = re.sub(r'[#*_~`>\-]', '', text).strip()
    if len(cleaned) <= length:
        return cleaned
    return cleaned[:length].rsplit(' ', 1)[0] + '...'


def generate_title(text):
    """Generate a short, meaningful title from the first user message (max 35 chars)."""
    cleaned = text.strip()
    prefixes = [
        'Explain ', 'explain ', 'Explain me ', 'explain me ',
        'Write ', 'write ',
        'Create ', 'create ',
        'What is ', 'what is ', 'What are ', 'what are ',
        'Who is ', 'who is ', 'Who are ', 'who are ',
        'How to ', 'how to ', 'How do I ', 'how do i ', 'How can I ', 'how can i ',
        'Generate ', 'generate ',
        'Tell me about ', 'tell me about ',
        'Can you ', 'can you ', 'Could you ', 'could you ',
        'Please ', 'please ',
        'I want to ', 'i want to ', 'I need to ', 'i need to ',
        'Help me ', 'help me ',
        'Give me ', 'give me ',
        'Show me ', 'show me ',
        'Make ', 'make ',
        'Build ', 'build ',
        'Define ', 'define ',
        'Describe ', 'describe ',
        'List ', 'list ',
        'Compare ', 'compare ',
        'Analyze ', 'analyze ',
        'Summarize ', 'summarize ',
    ]
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break

    cleaned = re.sub(r'[#*_~`>\-]', '', cleaned).strip()
    if not cleaned:
        cleaned = text.strip()[:35]

    if len(cleaned) <= 35:
        return cleaned
    return cleaned[:35].rsplit(' ', 1)[0] + '...'
