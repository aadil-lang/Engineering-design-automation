from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Mechanical Engineering Drawing Intelligence API")

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Mechanical Engineering Drawing Intelligence"}
