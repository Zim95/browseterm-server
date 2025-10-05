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
app.add_api_route(path="/login", endpoint=handlers.login, methods=["GET"])

# containers
app.add_api_route(path="/create_container", endpoint=handlers.create_container, methods=["POST"])
# app.add_api_route(path="/list_container", endpoint=handlers.list_container, methods=["GET"])
# app.add_api_route(path="/get_container", endpoint=handlers.get_container, methods=["GET"])
# app.add_api_route(path="/delete_container", endpoint=handlers.delete_container, methods=["DELETE"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
