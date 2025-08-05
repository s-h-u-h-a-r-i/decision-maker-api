from src.config import create_app
from src.config import settings


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_dev,
    )
