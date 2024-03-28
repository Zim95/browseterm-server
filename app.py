# third party
import flask
import flask_cors
import dotenv

# modules
import src.controller as cn
import src.auth as au
# builtins
import os


# load env values if file exists
dotenv.load_dotenv(".env")

# app setup
app: flask.Flask = flask.Flask(__name__)
controller: cn.Controller = cn.Controller()

# cors setup
cors: flask_cors.CORS = flask_cors.CORS(
    app,
    resources={
        r"/*": {
            "origins": "http://localhost:8001"
        }
    }
)

# authlib setup
au.configure_google_auth(app)
app.secret_key = os.environ.get("FLASK_SECRET")

# add routes
routes: list = [
    ("/ping", "ping", ["GET", "POST"]),
    ("/image_options", "image_options", ["GET"]),
    ("/google-login", "google_login", ["GET"]),
    ("/google-login-redirect", "google_login_redirect", ["GET"]),
]
for route in routes:
    app.add_url_rule(route[0], route[1], controller.handle, methods=route[2])


if __name__ == "__main__":
    app.run("0.0.0.0", port=8004, debug=True)
