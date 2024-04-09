# modules
import src.handlers.base_handler as bh
import src.auth as auth
# builtins
import blinker
import datetime as dt


usl_event = blinker.signal("update-session-lifetime")


class USLHandler(bh.Handler):
    """
    Update session lifetime.

    Author: Namah Shrestha
    """

    def __init__(self, request_params: dict) -> None:
        super().__init__(request_params)

    @auth.auth_required
    def handle(self) -> dict | None:
        try:
            usl_event.send(dt.timedelta(minutes=30))
            return "sucess"
        except Exception as e:
            return str(e)
