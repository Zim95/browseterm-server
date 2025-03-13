# modules
import src.handlers.base_handler as bh
import src.auth as auth
import src.models as models

# third party
import flask

# builtins
import json


class ProfileHandler(bh.Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    @auth.auth_required
    def handle(self) -> dict | None:
        try:
            user_id: str = json.loads(flask.session.get("session_info", "{}")).get("user_id", "")
            user: dict = models.user_model_ops.find({"id": user_id}, format_dict=True)
            del user["_sa_instance_state"]
            return user
        except Exception as e:
            raise Exception(e)
