# builtins
import os

# module
import src.handlers.base_handler as bh
import src.authconf as authconf


class LoginHandler(bh.Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_base_uri(self) -> str:
        base_uri: str = os.environ.get("BASE_URL", "")
        if not base_uri:
            raise ValueError("Invalid Base URI")
        return base_uri

    def get_redirect_uri_offset(self) -> str:
        raise NotImplementedError("Please implement the get_redirect_uri_offset method!")

    def get_redirect_uri(self) -> None:
        try:
            return self.get_base_uri() + self.get_redirect_uri_offset()
        except ValueError as ve:
            raise ValueError(ve)
        except NotImplementedError as ni:
            raise NotImplementedError(ni)

    def get_authorizer(self) -> any:
        raise NotImplementedError("Please implement the ger_authorizer method!")

    def handle(self) -> dict | None:
        try:
            redirect_uri: str = self.get_redirect_uri()
            authorizer: any = self.get_authorizer()
            return authorizer.authorize_redirect(redirect_uri=redirect_uri)
        except ValueError as ve:
            raise ValueError(ve)
        except NotImplementedError as ni:
            raise NotImplementedError(ni)


class GoogleLoginHandler(LoginHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_redirect_uri_offset(self) -> str:
        return "google-login-redirect"

    def get_authorizer(self) -> any:
        return authconf.oauth.BrowseTermGoogleAuth


class GithubLoginHandler(LoginHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_redirect_uri_offset(self) -> str:
        return "github-login-redirect"

    def get_authorizer(self) -> any:
        return authconf.oauth.BrowseTermGithubAuth
