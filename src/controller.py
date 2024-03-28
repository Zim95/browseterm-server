# third party
import flask
# builtins
import typing
# modules
import src.handlers as handlers


HANDLERS_MAP: dict = {
    "image_options": handlers.ImageOptionsHandler,
    "ping": handlers.PingHandler,
    "google-login": handlers.GoogleLoginHandler,
    "google-login-redirect": handlers.GoogleRedirectHandler,
}


class Controller:
    """
    Controls the route logic.
    1. Extracts request data.
    2. Sends the request data to appropriate handler methods
        based on route.
    3. Returns the response of the handler.
    4. Handles exceptions.

    Author: Namah Shrestha
    """

    def get_request_params(self, **kwargs: dict) -> dict:
        """
        Extract all request data.

        Author: Namah Shrestha
        """
        request_params: dict = {
            "query_params": dict(flask.request.args),
            "headers": dict(flask.request.headers),
            "payload": flask.request.data.decode("utf-8"),
            "form_data": dict(flask.request.form),
            "view_args": kwargs,
        }
        return request_params

    def handle(self, **kwargs: dict) -> typing.Any:
        """
        1. Sends the request data to appropriate handler methods
            based on route.
        2. Returns the response of the handler.
        3. Handles exceptions.
        Author: Namah Shrestha
        """
        try:
            request_params: dict = self.get_request_params(**kwargs)
            handler_name: str = flask.request.path
            if handler_name != "/":
                handler_name: str = handler_name.split("/")[1]
            handler: handlers.Handler = HANDLERS_MAP.get(
                handler_name, None
            )
            if not handler:
                return flask.jsonify(
                    {
                        "error": f"Invalid route: {handler_name}"
                    }
                ), 404
            # return flask.jsonify(
            #     {
            #         "response": handler(
            #             request_params=request_params).handle()
            #     }
            # ), 200
            return handler(request_params=request_params).handle()
        except Exception as e:
            return flask.jsonify(
                {
                    "error": f"Internal Server Error: {e}"
                }
            ), 500
