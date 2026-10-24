import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request

from app.config import get_log_level

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    level = get_log_level()
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    logger.setLevel(level)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def correlate_request(request: Request, call_next):
    request_id = str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info("request_id=%s status=%s", request_id, response.status_code)
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
