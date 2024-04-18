# module
import src.handlers.base_handler as bh
import src.authconf as authconf
import src.models as models
import src.models.commons as modcoms

# third party
import flask
import requests
import google.auth.jwt as jwt

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

    def extract_user_info(self, token_dict: dict) -> dict:
        raise NotImplementedError("Please implement extrac_user_info!")

    def handle(self) -> dict | None:
        """
        Author: Namah Shrestha
        """
        try:
            code: dict = self.get_code()
            client_info: dict = self.get_client_info()
            token_exchange_data: dict = {
                'code': code,
                'client_id': client_info["client_id"],
                'client_secret': client_info["client_secret"],
                'redirect_uri': client_info["redirect_uri"],
                'grant_type': 'authorization_code'
            }
            token_dict: dict = requests.post(
                client_info["access_token_url"],
                data=token_exchange_data
            ).json()

            # extract user info
            user_info_dict: dict = self.extract_user_info(token_dict)

            # insert or update user into db
            record: modcoms.decl.DeclarativeMeta = models.user_model_ops.insert_or_update_user(
                user_info=user_info_dict,
                return_record=True
            )

            # create session
            session_info = {"user_id": record.id}
            flask.session["session_info"] = json.dumps(session_info)

            # redirect to front end
            return {"response": user_info_dict}
        except NotImplementedError as ni:
            raise NotImplementedError(ni)
        except Exception as e:
            raise Exception(e)


class GoogleTokenExchangeHandler(TokenExchangeHandler):

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

    def extract_user_info(self, token_dict: str) -> dict:
        try:
            # tokens
            id_token: str = token_dict["id_token"]
            access_token: str = token_dict["access_token"]

            # person data
            person_data_url: str = os.environ.get("GOOGLE_AUTH_PERSON_DATA_URL", "")
            person_data: dict = requests.get(
                person_data_url,
                headers={
                    "Authorization": f"Bearer {access_token}"
                }
            ).json()

            # user data
            user_info: dict = jwt.decode(id_token, verify=False)

            # user info dict
            user_info_dict: dict = {
                "email": user_info["email"],
                "name": user_info["name"],
                "profile_picture_url": user_info["picture"],
                "birthday": self.extract_birthday(
                    person_data.get("birthdays", [])
                ),
                "gender": self.extract_gender(
                    person_data.get("genders", [])
                )
            }
            return user_info_dict
        except Exception as e:
            raise Exception(e)

    def get_client_info(self) -> dict:
        return {
            "client_id": os.environ.get("GOOGLE_AUTH_CLIENT_ID"),
            "client_secret": os.environ.get("GOOGLE_AUTH_CLIENT_SECRET"),
            "redirect_uri": os.environ.get("GOOGLE_AUTH_REDIRECT_URI"),
            "access_token_url": os.environ.get("GOOGLE_ACCESS_TOKEN_URL")
        }


class GithubTokenExchangeHandler(TokenExchangeHandler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    def get_client_info(self) -> dict:
        return {
            "client_id": os.environ.get("GITHUB_AUTH_CLIENT_ID"),
            "client_secret": os.environ.get("GITHUB_AUTH_CLIENT_SECRET"),
            "redirect_uri": os.environ.get("GITHUB_AUTH_REDIRECT_URI"),
            "access_token_url": os.environ.get("GITHUB_ACCESS_TOKEN_URL")
        }
