from fastapi import FastAPI

app = FastAPI(
    title="Decision Maker API",
    description="API for decision making app",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Decisin Maker API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
