import re


def sanitize_message(content):
    return content.strip()[:10000]


def truncate_title(text, length=50):
    cleaned = re.sub(r'[#*_~`>\-]', '', text).strip()
    if len(cleaned) <= length:
        return cleaned
    return cleaned[:length].rsplit(' ', 1)[0] + '...'
