import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import sample
from app.api import advice, credentials, health, jobs, profiles, runs, tailor
from app.core.config import settings
from app.core.llm import LLMError
from app.core.logging import setup_logging
from app.db.session import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    try:
        with SessionLocal() as db:
            sample.seed(db)
    except SQLAlchemyError as e:
        # A database that is down must not stop the app from starting. It still answers
        # /health, which is where the reason shows up; seeding runs again on the next start.
        logging.getLogger("careerpilot").error(
            "demo data not seeded, the database did not answer: %s", type(e).__name__
        )
    yield


app = FastAPI(title="CareerPilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
def llm_failed(request, exc: LLMError):
    # LLMError messages never carry prompt or response text, so they are safe to log
    logging.getLogger("careerpilot").error("%s %s: %s", request.method, request.url.path, exc)
    return JSONResponse({"detail": "The AI step failed. Please try again."}, status_code=502)


app.include_router(health.router)
app.include_router(profiles.router)
app.include_router(jobs.router)
app.include_router(tailor.router)
app.include_router(advice.router)
app.include_router(credentials.router)
app.include_router(runs.router)
