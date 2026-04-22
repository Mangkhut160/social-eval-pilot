from fastapi import Request

from src.models.user import User

SESSION_USER_ID_KEY = "user_id"
SESSION_AUTH_METHOD_KEY = "auth_method"


def login_user(request: Request, user: User) -> None:
    request.session.clear()
    request.session[SESSION_USER_ID_KEY] = user.id
    request.session[SESSION_AUTH_METHOD_KEY] = "session"


def logout_user(request: Request) -> None:
    request.session.clear()
