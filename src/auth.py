# builtins
import os

# third party
import flask
import authlib.integrations.flask_client as oauth_flask


# main object
oauth: oauth_flask.OAuth = oauth_flask.OAuth()


# configure google auth
def configure_google_auth(app: flask.Flask) -> None:
    oauth.register(
        "BrowseTermGoogleAuth",
        client_id=os.environ.get("GOOGLE_AUTH_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_AUTH_CLIENT_SECRET"),
        server_metadata_url=os.environ.get("GOOGLE_AUTH_META_URL"),
        client_kwargs={
            "scope": "openid profile email https://www.googleapis.com/auth/user.birthday.read https://www.googleapis.com/auth/user.gender.read"
        }  
    )
    oauth.init_app(app)
