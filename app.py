# third party
import flask
import flask_cors

# modules
import src.controller as cn


# setup
app: flask.Flask = flask.Flask(__name__)
controller: cn.Controller = cn.Controller()
cors: flask_cors.CORS = flask_cors.CORS(
    app,
    resources={
        r"/*": {
            "origins": "http://localhost:8001"
        }
    }
)


# add routes
routes: list = [
    ("/ping", "ping", ["GET", "POST"]),
    ("/image_options", "image_options", ["GET"])
]
for route in routes:
    app.add_url_rule(route[0], route[1], controller.handle, methods=route[2])


if __name__ == "__main__":
    app.run("0.0.0.0", port=8004, debug=True)
