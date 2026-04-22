class SocialEvalError(Exception):
    pass


class IngestionError(SocialEvalError):
    pass


class KnowledgeError(SocialEvalError):
    pass


class EvaluationError(SocialEvalError):
    pass


class ProviderCallError(EvaluationError):
    def __init__(self, provider: str, message: str):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider


class AuthError(SocialEvalError):
    pass


class NotFoundError(SocialEvalError):
    pass
