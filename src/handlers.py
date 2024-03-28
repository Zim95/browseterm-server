# builtins
import abc
import os

# module
import src.auth as au


class Handler:
    """
    Handler abstract class. Receives request data.
    Has a handle method which is an abstract class method.

    Author: Namah Shrestha
    """

    def __init__(self, request_params: dict) -> None:
        """
        Initialize the request params.

        Author: Namah Shrestha
        """
        self.request_params: dict = request_params

    @abc.abstractclassmethod
    def handle(self) -> dict | None:
        """
        Abstract handle logic to be implemented by child classes.

        Author: Namah Shrestha
        """
        pass


class PingHandler(Handler):
    """
    Simple Ping Handler. For test.
    Accepts request parameters.
    Echoes back request parameters and runtime environment.

    Author: Namah Shrestha
    """
    def __init__(self, request_params: dict) -> None:
        """
        Initialize request parameters.

        Author: Namah Shrestha
        """
        super().__init__(request_params)
    
    def handle(self) -> dict | None:
        """
        Return request params for test.

        Author: Namah Shrestha
        """
        return {
            "request_params": self.request_params,
        }


class ImageOptionsHandler(Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)
    
    def handle(self) -> dict | None:
        return [
            {
                "id": "asdfghjkl",
                "value": "zim95/ssh_ubuntu:latest",
                "label": "ubuntu",
            }
        ]


class LoginHandler(Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_base_uri(self) -> str:
        base_uri: str = os.environ.get("BASE_URL", "")
        if not base_uri:
            raise ValueError("Invalid Base URI")
        return base_uri

    def get_redirect_uri_offset(self) -> str:
        return ""

    def get_redirect_uri(self) -> None:
        try:
            return self.get_base_uri() + self.get_redirect_uri_offset()
        except ValueError as ve:
            raise ValueError(ve)

    def handle(self) -> dict | None:
        redirect_uri: str = self.get_redirect_uri()
        return au.oauth.BrowseTermGoogleAuth.authorize_redirect(redirect_uri=redirect_uri)


class GoogleLoginHandler(LoginHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_redirect_uri_offset(self) -> str:
        return "google-login-redirect"


class GoogleRedirectHandler(Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def handle(self) -> dict | None:
        token: str = au.oauth.BrowseTermGoogleAuth.authorize_access_token()
        breakpoint()
        # app.flask.session
