# builtins
import functools
import time
import os

# third party
import flask.sessions as sessions
import google.auth as gauth


class AuthValidator:

    def __init__(self) -> None:
        self.session = self.load_session()

    def load_session(self) -> dict:
        return {}

    def validate_session(self) -> bool:
        raise NotImplementedError("Please implement validate session method!")    


class GoogleAuthValidator(AuthValidator):

    def __init__(self) -> None:
        super().__init__()

    def validate_session(self) -> bool:
        try:
            id_token: str = self.session.get("token_info", {}).get("id_token", "")
            if not id_token:
                return "No token available", False
            id_info = gauth.jwt.decode(id_token, verify=False)
            # Check if the token has expired
            if id_info['exp'] < time.time():
                return 'Token has expired', False
            # Optionally, verify other claims such as audience and issuer
            if id_info['aud'] != os.environ.get("GOOGLE_AUTH_CLIENT_ID"):
                return 'Invalid client id', False
            if id_info['iss'] != 'https://accounts.google.com':
                return 'Invalid issuer', False
            return "Verified", True
        except Exception as e:
            return str(e), False


class GithubAuthValidator(AuthValidator):
    def __init__(self) -> None:
        super().__init__()


class AuthlabAuthValidator(AuthValidator):
    def __init__(self) -> None:
        super().__init__()


AUTH_PROVIDER_VALIDATOR_MAP: dict = {
    "google": GoogleAuthValidator,
    "github": GithubAuthValidator,
    "authlab": AuthlabAuthValidator,
}


def auth_required(handler: callable) -> callable:
    @functools.wraps
    def wrapper(*args: tuple, **kwargs: dict) -> any:
        """
        1. Retrieve Session.
        2. Get the auth provider in the session. i.e. google/github/authlab.
        3. Based on the auth provider call the respective auth class's validator.
        """
        pass

    return wrapper