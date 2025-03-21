from fastapi import FastAPI
import uvicorn
# import all handlers
import src.handlers as handlers

app = FastAPI()


app.add_api_route(path="/echo", endpoint=handlers.echo, methods=["POST"])
app.add_api_route(path="/create_container", endpoint=handlers.create_container, methods=["POST"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9999)
