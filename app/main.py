from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import psycopg

from app.db import check_db_health, init_db
from app.models_read import HealthResponse, RunReadResponse
from app.models_write import RunCreateRequest
from app.services_read import list_all_runs
from app.services_write import create_or_update_run


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Celesto Run Ledger API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "invalid_request", "details": exc.errors()},
    )


@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def get_health():
    if not check_db_health():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    return {"status": "ok"}


@app.get("/api/runs", response_model=list[RunReadResponse], status_code=status.HTTP_200_OK)
def get_runs():
    return list_all_runs()


@app.post("/api/runs", response_model=RunReadResponse, status_code=status.HTTP_201_CREATED)
def post_run(payload: RunCreateRequest):
    try:
        row = create_or_update_run(payload)
        return row
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
