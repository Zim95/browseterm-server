# builtins
import functools

# third party
import flask.sessions as sessions


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