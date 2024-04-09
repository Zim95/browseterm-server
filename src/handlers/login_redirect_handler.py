# module
import src.handlers.base_handler as bh
import src.authconf as authconf
import src.models as models

# third party
import flask
import requests

# builtins
import os
import json


class LoginRedirectHandler(bh.Handler):
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

    def get_token(self) -> dict:
        """
        Get token

        Author: Namah Shrestha
        """
        raise NotImplementedError(
            "Please implement the get_token method!")

    def extract_user_info(self, token: dict) -> dict:
        """
        Extract user info from token

        Author: Namah Shrestha
        """
        raise NotImplementedError(
            "Please implement the extract_user_info method!")

    def extract_agent_info(self) -> dict:
        return {
            "user_agent": self.request_params.get(
                "headers", {}).get("User-Agent", ""),
            "host": self.request_params.get(
                "headers", {}).get("Host", "")
        }

    def handle(self) -> dict | None:
        """
        1. Construct token.
        2. Construct user info.
        3. Construct agent info
        4. Insert or Update user info.
        5. Update token info in session.

        Author: Namah Shrestha
        """
        try:
            token: dict = self.get_token()
            user_info: dict = self.extract_user_info(token)
            # insert user_info into the database
            agent_info: dict = self.extract_agent_info()
            session_info = {"user_info": user_info, "agent_info": agent_info}
            flask.session["session_info"] = json.dumps(session_info)
            return flask.redirect("http://localhost:8004/ping")
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

    def get_person_data(self, access_token: str) -> dict:
        try:
            person_data_url: str = os.environ.get("GOOGLE_AUTH_PERSON_DATA_URL", "")
            person_data: dict = requests.get(
                person_data_url,
                headers={
                    "Authorization": f"Bearer {access_token}"
                }
            ).json()
            return person_data
        except Exception:
            return {}

    def get_token(self) -> dict:
        try:
            token: dict = authconf.oauth.BrowseTermGoogleAuth.authorize_access_token()
            person_data=self.get_person_data(access_token=token['access_token'])
            token["person_data"] = person_data
            return token
        except Exception as e:
            raise Exception(e)


class GithubLoginRedirectHandler(LoginRedirectHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def extract_user_info(self, token: dict) -> dict:
        return {
            "name": token["userinfo"]["name"],
            "email": token["userinfo"]["email"],
            "profile_picture_url": token["userinfo"].get("avatar_url", ""),
            "location": token["userinfo"].get("location", "")
        }

    def get_token(self) -> dict:
        access_token: dict = authconf.oauth.BrowseTermGithubAuth.authorize_access_token()
        user_info: dict = authconf.oauth.BrowseTermGithubAuth.get("user").json()
        return {**access_token, "userinfo": user_info}
