# modules
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# local
import src.template_handlers as template_handlers
import src.api_handlers as api_handlers
from src.status_listener import status_listener_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    # Startup: Start the status listener service
    loop = asyncio.get_event_loop()
    status_listener_service.start(loop)
    yield
    # Shutdown: Stop the status listener service
    status_listener_service.stop()


app = FastAPI(lifespan=lifespan)

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
app.add_api_route(path="/get-container-info/{container_id}", endpoint=api_handlers.get_container_info, methods=["GET"])
app.add_api_route(path="/create-container-in-db", endpoint=api_handlers.create_container_in_db, methods=["POST"])
app.add_api_route(path="/create-container-in-k8s", endpoint=api_handlers.create_container_in_k8s, methods=["POST"])
app.add_api_route(path="/update-container", endpoint=api_handlers.update_container, methods=["POST"])
app.add_api_route(path="/list-user-containers", endpoint=api_handlers.list_user_containers, methods=["GET"])
app.add_api_route(path="/delete-container-in-db", endpoint=api_handlers.delete_container_in_db, methods=["POST"])
app.add_api_route(path="/delete-container-in-k8s", endpoint=api_handlers.delete_container_in_k8s, methods=["POST"])
app.add_api_route(path="/save-container", endpoint=api_handlers.save_container, methods=["POST"])

# SSE endpoints for real-time updates
app.add_api_route(path="/container-status-stream", endpoint=api_handlers.container_status_sse, methods=["GET"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
