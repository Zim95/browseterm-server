# module
import src.handlers.base_handler as bh
import src.authconf as authconf
import src.models as models
import src.models.commons as modcoms

# third party
import flask
import requests

# builtins
import os
import json


class TokenExchangeHandler(bh.Handler):
    """
    Handle Login Redirect.

    Author: Namah Shrestha
    """

    def __init__(self, request_params: dict) -> None:
        """
        Initialize request params.
        :params:
            :request_params: dict: Request parameters.
        :returns: None

        Author: Namah Shrestha
        """
        super().__init__(request_params)

    def get_code(self) -> str:
        payload_string: str = self.request_params.get("payload", "")
        if not payload_string:
            return payload_string
        payload: dict = json.loads(payload_string)
        return payload.get("code", "")

    def get_client_info(self) -> dict:
        raise NotImplementedError("Please implement get_client_info!")

    def handle(self) -> dict | None:
        """
        Author: Namah Shrestha
        """
        try:
            # code info
            code: dict = self.get_code()
            client_info: dict = self.get_client_info()
            token_exchange_data: dict = {
                'code': code,
                'client_id': client_info["client_id"],
                'client_secret': client_info["client_secret"],
                'redirect_uri': 'postmessage',
                'grant_type': 'authorization_code'
            }
            response: dict = requests.post(
                'https://oauth2.googleapis.com/token',
                data=token_exchange_data
            ).json()
            breakpoint()
        except NotImplementedError as ni:
            raise NotImplementedError(ni)
        except Exception as e:
            raise Exception(e)


class GoogleTokenExchangeHandler(TokenExchangeHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_client_info(self) -> dict:
        return {
            "client_id": os.environ.get("GOOGLE_AUTH_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_AUTH_CLIENT_SECRET")
        }


class GithubTokenExchangeHandler(TokenExchangeHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_client_info(self) -> dict:
        return {
            "client_id": os.environ.get("GITHUB_AUTH_CLIENT_ID"),
            "client_secret": os.environ.get("GITHUB_AUTH_CLIENT_SECRET")
        }
