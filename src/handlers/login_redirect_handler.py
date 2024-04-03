# module
import src.handlers.base_handler as bh
import src.authconf as authconf

# third party
import flask


class LoginRedirectHandler(bh.Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_token(self) -> dict:
        raise NotImplementedError("Please implement the get_token method!")

    def get_user_info(self) -> dict:
        """
        Extract user info from token
        """
        raise NotImplementedError("Please implement the get_user_info method!")

    def handle(self) -> dict | None:
        try:
            token: dict = self.get_token()
            breakpoint()
            flask.session["user"] = token
        except NotImplementedError as ni:
            raise NotImplementedError(ni)


class GoogleLoginRedirectHandler(LoginRedirectHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_token(self) -> dict:
        return authconf.oauth.BrowseTermGoogleAuth.authorize_access_token()
