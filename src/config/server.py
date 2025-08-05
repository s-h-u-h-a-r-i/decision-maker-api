from fastapi import FastAPI
from .settings import settings


def create_app() -> FastAPI:
    app = FastAPI(debug=settings.is_dev, title="Decision Maker API")

    @app.get("/")
    async def read_root() -> dict[str, str]:
        return {"hello": "world"}

    return app


__all__ = ["create_app"]
