# builtins
import functools
import json
# third party
import flask


def auth_required(handler: callable) -> callable:
    @functools.wraps(handler)
    def wrapper(*args: tuple, **kwargs: dict) -> any:
        """
        1. Retrieve Session.
        2. If session data is not present, it has expired, send result.
        3. If session exists.
            - Validate host and agent; return "unauthorized" if necessary.
            - Add userinfo on requests and then call handler.
        Author: Namah Shrestha
        """
        session_data: dict = json.loads(flask.session.get("session_info", '{}'))
        if not session_data:
            # after expirty the session data disappears.
            # we do not need to check the lifetime.
            # This case is when the session data has disappeared.
            return "Unauthorized", 401
        # validate agent and host
        # inspect args and kwargs
        breakpoint()
        return handler(*args, **kwargs)
    return wrapper
