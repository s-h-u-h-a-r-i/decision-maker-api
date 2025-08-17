import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import setup_logging, get_settings, Settings

setup_logging()
settings: Settings = get_settings()

logger: logging.Logger = logging.getLogger(__name__)

app = FastAPI(
    title="Decision Maker API",
    description="API for decision making app",
    version="0.1.0",
)

app.add_middleware(
    middleware_class=CORSMiddleware,
    allow_origins=["http://192.168.0.3"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Decisin Maker API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_config=None,
    )
