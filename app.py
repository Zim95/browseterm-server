# modules
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# local
import src.template_handlers as template_handlers
import src.api_handlers as api_handlers


app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="templates/static"), name="static")

# health checkup
app.add_api_route(path="/echo", endpoint=api_handlers.echo, methods=["POST"])

# application templates
app.add_api_route(path="/", endpoint=template_handlers.home, methods=["GET"])
app.add_api_route(path="/terminals", endpoint=template_handlers.terminals, methods=["GET"])
app.add_api_route(path="/terminalpage", endpoint=template_handlers.terminalpage, methods=["GET"])
app.add_api_route(path="/subscriptions", endpoint=template_handlers.subscriptions, methods=["GET"])
app.add_api_route(path="/profile", endpoint=template_handlers.profile, methods=["GET"])
app.add_api_route(path="/login", endpoint=template_handlers.login, methods=["GET"])

# authentication templates
app.add_api_route(path="/google-login-redirect", endpoint=template_handlers.google_login_redirect, methods=["GET"])
app.add_api_route(path="/github-login-redirect", endpoint=template_handlers.github_login_redirect, methods=["GET"])

# hidden routes (not in sidebar)
app.add_api_route(path="/js-test", endpoint=template_handlers.js_test, methods=["GET"])

# authentication apis
app.add_api_route(path="/google-token-exchange", endpoint=api_handlers.google_token_exchange, methods=["POST"])
app.add_api_route(path="/github-token-exchange", endpoint=api_handlers.github_token_exchange, methods=["POST"])
app.add_api_route(path="/logout", endpoint=api_handlers.logout, methods=["POST"])

# container apis
app.add_api_route(path="/create_container", endpoint=api_handlers.create_container, methods=["POST"])
# app.add_api_route(path="/list_container", endpoint=handlers.list_container, methods=["GET"])
# app.add_api_route(path="/get_container", endpoint=handlers.get_container, methods=["GET"])
# app.add_api_route(path="/delete_container", endpoint=handlers.delete_container, methods=["DELETE"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
