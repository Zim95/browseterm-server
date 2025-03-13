"""
Useless utils I use while debugging.
"""

# third-party
import redis
from google.auth import jwt
# built-ins
import os


def check_session_lifetime(session_id: str) -> int:
    rc: redis.Redis = redis.Redis(
        host=os.environ.get("REDIS_SESSION_HOST", "localhost"),
        port=os.environ.get("REDIS_SESSION_PORT", 6379),
        db=os.environ.get("REDIS_SESSION_DB", 0)
    )
    redis_id: str = f"session:{session_id}"
    return rc.ttl(redis_id)


def check_all_sessions() -> None:
    rc: redis.Redis = redis.Redis(
        host=os.environ.get("REDIS_SESSION_HOST", "localhost"),
        port=os.environ.get("REDIS_SESSION_PORT", 6379),
        db=os.environ.get("REDIS_SESSION_DB", 0)
    )
    redis_keys: list = rc.keys()
    for redis_key in redis_keys:
        breakpoint()
        key: str = redis_key.decode('utf-8')


def decode_token(token: str) -> str:
    try:
        print(jwt.decode(token, verify=False))
    except Exception as e:
        print(e)
