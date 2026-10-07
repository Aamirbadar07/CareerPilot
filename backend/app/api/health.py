from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    """Whether this process is up, and whether its database answers.

    Always 200, even when the database is down: Cloud Run and Render restart a container
    whose health check fails, and restarting cannot fix someone else's database. The code
    says the process is alive; `status` in the body says whether it can do any work.
    """
    try:
        db.execute(text("select 1"))
    except SQLAlchemyError as e:
        # the class name only: a connection error's message can carry the host and user
        return {"status": "degraded", "database": f"unreachable ({type(e).__name__})"}
    return {"status": "ok", "database": "ok"}
