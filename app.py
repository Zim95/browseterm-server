# modules
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# local
import src.handlers as handlers


app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# health checkup
app.add_api_route(path="/echo", endpoint=handlers.echo, methods=["POST"])

# template routes
app.add_api_route(path="/", endpoint=handlers.home, methods=["GET"])
app.add_api_route(path="/terminals", endpoint=handlers.terminals, methods=["GET"])
app.add_api_route(path="/terminalpage", endpoint=handlers.terminalpage, methods=["GET"])
app.add_api_route(path="/subscriptions", endpoint=handlers.subscriptions, methods=["GET"])
app.add_api_route(path="/profile", endpoint=handlers.profile, methods=["GET"])
app.add_api_route(path="/login", endpoint=handlers.login, methods=["GET"])

# authentication routes
app.add_api_route(path="/google-login-redirect", endpoint=handlers.google_login_redirect, methods=["GET"])
app.add_api_route(path="/github-login-redirect", endpoint=handlers.github_login_redirect, methods=["GET"])

# OAuth token exchange routes
app.add_api_route(path="/google-token-exchange", endpoint=handlers.google_token_exchange, methods=["POST"])
app.add_api_route(path="/github-token-exchange", endpoint=handlers.github_token_exchange, methods=["POST"])

# Logout route
app.add_api_route(path="/logout", endpoint=handlers.logout, methods=["POST"])

# containers
app.add_api_route(path="/create_container", endpoint=handlers.create_container, methods=["POST"])
# app.add_api_route(path="/list_container", endpoint=handlers.list_container, methods=["GET"])
# app.add_api_route(path="/get_container", endpoint=handlers.get_container, methods=["GET"])
# app.add_api_route(path="/delete_container", endpoint=handlers.delete_container, methods=["DELETE"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
