from fastapi import FastAPI

from app.api import health

app = FastAPI(title="CareerPilot")
app.include_router(health.router)
