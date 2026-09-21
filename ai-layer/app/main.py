from fastapi import FastAPI

from app.api.ingest import router as ingest_router
from app.api.query import router as query_router
from app.config import settings

#creates your actual FastAPI application.
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)


app.include_router(ingest_router)
app.include_router(query_router)


@app.get("/")
def root():

    return {
        "service": settings.app_name,
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }