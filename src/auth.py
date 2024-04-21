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
        # headers: dict = [*args][0].request_params["headers"]
        # host: str = headers.get("Host", "")
        # user_agent: str = headers.get("User-Agent", "")
        # agent_info: dict = session_data["agent_info"]
        # if host != agent_info["host"] or user_agent != agent_info["user_agent"]:
        #     # if host and user agent mismach, raise Unauthorized
        #     return "Unauthorized", 401

        return handler(*args, **kwargs)
    return wrapper
