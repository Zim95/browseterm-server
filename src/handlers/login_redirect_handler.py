# module
import src.handlers.base_handler as bh
import src.authconf as authconf
import src.models as models

# third party
import flask
import requests

# builtins
import os


class LoginRedirectHandler(bh.Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_token(self) -> dict:
        raise NotImplementedError("Please implement the get_token method!")

    def extract_user_info(self, token: dict) -> dict:
        """
        Extract user info from token
        """
        raise NotImplementedError("Please implement the extract_user_info method!")

    def extract_token_info(self, token: dict) -> dict:
        """
        Extract token info from token
        """
        raise NotImplementedError("Please implement the extract_token_info method!")

    def handle(self) -> dict | None:
        try:
            token: dict = self.get_token()
            user_info: dict = self.extract_user_info(token)
            token_info: dict = self.extract_token_info(token)
            breakpoint()
            flask.session["token_info"] = token_info
        except NotImplementedError as ni:
            raise NotImplementedError(ni)


class GoogleLoginRedirectHandler(LoginRedirectHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def extract_birthday(self, birthdays: list) -> str:
        dateslot: list = ["", "", ""]
        for birthday in birthdays:
            date: dict = birthday["date"]
            y: str = str(date.get("year", ""))
            m: str = str(date.get("month", ""))
            d: str = str(date.get("day", ""))
            dateslot[0] = y if not dateslot[0] or y!=dateslot[0] else dateslot[0]
            dateslot[1] = m if not dateslot[1] or m!=dateslot[1] else dateslot[1]
            dateslot[2] = d if not dateslot[2] or d!=dateslot[2] else dateslot[2]
        return "-".join(dateslot)

    def extract_gender(self, genders: list) -> str:
        g: str = ""
        for gender in genders:
            g = gender["value"] if not g or g!=gender["value"] else g
        return g

    def extract_user_info(self, token: dict) -> dict:
        return {
            "name": token["userinfo"]["name"],
            "email": token["userinfo"]["email"],
            "profile_picture_url": token["userinfo"].get("picture", ""),
            "birthday": self.extract_birthday(
                token["person_data"].get("birthdays", [])
            ),
            "gender": self.extract_gender(
                token["person_data"].get("genders", [])
            )
        }

    def extract_token_info(self, token: dict) -> dict:
        return {
            "token_info": {
                "id_token": token["id_token"]
            },
            "provider": "google"
        }

    def get_token(self) -> dict:
        token: dict = authconf.oauth.BrowseTermGoogleAuth.authorize_access_token()
        person_data_url: str = os.environ.get("GOOGLE_AUTH_PERSON_DATA_URL", "")
        person_data: dict = requests.get(
            person_data_url,
            headers={
                "Authorization": f"Bearer {token['access_token']}"
            }
        ).json()
        token["person_data"] = person_data
        return token


class GithubLoginRedirectHandler(LoginRedirectHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def extract_user_info(self, token: dict) -> dict:
        return {
            "name": token["userinfo"]["name"],
            "email": token["userinfo"]["email"],
            "profile_picture_url": token["userinfo"].get("avatar_url", "")
        }

    def extract_token_info(self, token: dict) -> dict:
        return {
            "access_token": "",
            "id_token": "",
            "expires_in": "",
            "expires_at": "",
            "token_type": "",
            "provider": "github"
        }

    def get_token(self) -> dict:
        access_token: dict = authconf.oauth.BrowseTermGithubAuth.authorize_access_token()
        user_info: dict = authconf.oauth.BrowseTermGithubAuth.get("user").json()
        return {**access_token, "userinfo": user_info}
