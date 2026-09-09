from fastapi import FastAPI

from .core.database import Base, engine
from .models.traffic_event import TrafficEvent
from .api.traffic import router as traffic_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RouteX API")

app.include_router(traffic_router)


@app.get("/")
def root():
    return {"message": "RouteX API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}