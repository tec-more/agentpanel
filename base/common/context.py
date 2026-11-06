from contextvars import ContextVar
from typing import Optional

current_user_id: ContextVar[Optional[int]] = ContextVar('current_user_id', default=None)
current_username: ContextVar[Optional[str]] = ContextVar('current_username', default=None)
current_trace_id: ContextVar[Optional[str]] = ContextVar('current_trace_id', default=None)


def set_user_context(user_id: Optional[int], username: Optional[str] = None):
    current_user_id.set(user_id)
    if username:
        current_username.set(username)


def clear_user_context():
    current_user_id.set(None)
    current_username.set(None)


def set_trace_id(trace_id: str):
    current_trace_id.set(trace_id)


def get_current_trace_id() -> Optional[str]:
    return current_trace_id.get()


def clear_trace_id():
    current_trace_id.set(None)
