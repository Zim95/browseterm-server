# builtins
import functools
import json
import os
# third party
import flask
import redis


def check_session_lifetime() -> int:
    rc: redis.Redis = redis.Redis(
        host=os.environ.get("REDIS_SESSION_HOST", "localhost"),
        port=os.environ.get("REDIS_SESSION_PORT", 6379),
        db=os.environ.get("REDIS_SESSION_DB", 0)
    )
    redis_id: str = f"session:{flask.session.sid}"
    return rc.ttl(redis_id)


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
        headers: dict = [*args][0].request_params["headers"]
        host: str = headers.get("Host", "")
        user_agent: str = headers.get("User-Agent", "")
        agent_info: dict = session_data["agent_info"]
        if host != agent_info["host"] or user_agent != agent_info["user_agent"]:
            # if host and user agent mismach, raise Unauthorized
            return "Unauthorized", 401

        return handler(*args, **kwargs)
    return wrapper
