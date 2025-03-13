# modules
import src.handlers.base_handler as bh
import src.auth as auth

# third party
import flask


class LogoutHandler(bh.Handler):

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    @auth.auth_required
    def handle(self) -> dict | None:
        try:
            flask.session.pop("session_info")
            return {"status": "logged out"}
        except Exception as e:
            raise Exception(e)
