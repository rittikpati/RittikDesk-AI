class AIAssistantError(Exception):
    pass


class AuthenticationError(AIAssistantError):
    pass


class RateLimitError(AIAssistantError):
    pass


class TimeoutError(AIAssistantError):
    pass


class ModelNotFoundError(AIAssistantError):
    pass


class ServerError(AIAssistantError):
    pass


class NetworkError(AIAssistantError):
    pass
