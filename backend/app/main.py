from fastapi import FastAPI

app = FastAPI(title="RouteX API")


@app.get("/")
def root():
    return {"message": "RouteX API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}