import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from api.routes import router

app = FastAPI(title="Mechanical Engineering Drawing Intelligence API")

# Ensure required static directories exist
ui_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui")
artifacts_dir = os.path.join(os.getcwd(), "artifacts")
os.makedirs(ui_dir, exist_ok=True)
os.makedirs(artifacts_dir, exist_ok=True)

# Mount artifacts and UI static files
# NOTE: Static mounting of /artifacts is intended for local single-user portfolio review.
# For production multi-tenant deployment, replace with project/user-authorized artifact access endpoints.
app.mount("/artifacts", StaticFiles(directory=artifacts_dir), name="artifacts")
app.mount("/ui", StaticFiles(directory=ui_dir, html=True), name="ui")

app.include_router(router)

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Mechanical Engineering Drawing Intelligence", "review_ui": "/ui"}

@app.get("/design-review")
def design_review():
    return RedirectResponse(url="/ui")
