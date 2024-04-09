# third party
import flask
import flask_cors
import flask_session
import dotenv
# modules
import src.controller as cn
import src.authconf as authconf
import src.auth as auth
import src.handlers.usl_handler as uh
# builtins
import os
import datetime as dt


# load env values if file exists
dotenv.load_dotenv(".env")

# app setup
app: flask.Flask = flask.Flask(__name__)
# flask session setup
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False  # Session will expire when the browser is closed
app.config['SESSION_USE_SIGNER'] = True  # Sign the session cookie for extra security
app.config['SESSION_REDIS'] = {  # Redis server configuration
    'host': os.environ.get("REDIS_SESSION_HOST"),
    'port': os.environ.get("REDIS_SESSION_PORT"),
    'db': os.environ.get("REDIS_SESSION_DB"),  # Redis database index
    'password': os.environ.get("REDIS_SESSION_PASSWORD")  # Optional: If Redis requires authentication
}
# additional session security
# app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = dt.timedelta(minutes=10)

server_session: flask_session.Session = flask_session.Session(app)
# authlib setup
authconf.configure_google_auth(app)
authconf.configure_github_auth(app)
app.secret_key = os.environ.get("FLASK_SECRET")

# cors setup
cors: flask_cors.CORS = flask_cors.CORS(
    app,
    resources={
        r"/*": {
            "origins": "http://localhost:8001"
        }
    }
)

# controllers
controller: cn.Controller = cn.Controller()

# add routes
routes: list = [
    ("/ping", "ping", ["GET", "POST"]),
    ("/image_options", "image_options", ["GET"]),
    ("/google-login", "google_login", ["GET"]),
    ("/github-login", "github_login", ["GET"]),
    ("/google-login-redirect", "google_login_redirect", ["GET"]),
    ("/github-login-redirect", "github_login_redirect", ["GET"]),
    ("/usl", "usl", ["GET"])
]
for route in routes:
    app.add_url_rule(
        route[0], route[1], controller.handle, methods=route[2])


# handle session update event here
def handle_usl_event(td: dt.timedelta) -> None:
    app.config['PERMANENT_SESSION_LIFETIME'] = td


uh.usl_event.connect(handle_usl_event)


if __name__ == "__main__":
    app.run("0.0.0.0", port=8004, debug=True)
