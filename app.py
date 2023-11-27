# third party
import flask

# modules
import src.controller as cn


# setup
app: flask.Flask = flask.Flask(__name__)
controller: cn.Controller = cn.Controller()

# add routes
routes: list = [
    ("/ping", "ping", ["GET", "POST"]),
    ("/image_options", "image_options", ["GET"])
]
for route in routes:
    app.add_url_rule(route[0], route[1], controller.handle, methods=route[2])


if __name__ == "__main__":
    app.run("0.0.0.0", port=8004, debug=True)
