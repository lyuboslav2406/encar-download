from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR
from .routes import router


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    return app
