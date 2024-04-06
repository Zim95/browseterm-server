# builtins
import os
import json

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
        client_kwargs=eval(os.environ.get("GOOGLE_CLIENT_KWARGS"))
    )
    oauth.init_app(app)


def configure_github_auth(app: flask.Flask) -> None:
    oauth.register(
        "BrowseTermGithubAuth",
        client_id=os.environ.get("GITHUB_AUTH_CLIENT_ID"),
        client_secret=os.environ.get("GITHUB_AUTH_CLIENT_SECRET"),
        access_token_url=os.environ.get("GITHUB_ACCESS_TOKEN_URL"),
        access_token_params=os.environ.get("GITHUB_ACCESS_TOKEN_PARAMS", None),
        authorize_url=os.environ.get("GITHUB_AUTHORIZE_URL"),
        authorize_params=os.environ.get("GITHUB_AUTHORIZE_PARAMS", None),
        api_base_url=os.environ.get("GITHUB_API_BASE_URL"),
        client_kwargs=eval(os.environ.get("GITHUB_CLIENT_KWARGS"))
    )
    oauth.init_app(app)
