import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router
from app.api.inventory import router as inventory_router
from app.api.ops import router as ops_router
from app.core.config import load_settings
from app.core.db import make_engine
from app.modules.identity.delivery import LocalDiscardDelivery

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()  # Reject production before any DB connection.
    logging.basicConfig(
        level=settings.log_level, format="%(levelname)s %(name)s %(message)s"
    )
    logger.setLevel(settings.log_level)
    app.state.settings = settings
    app.state.engine = make_engine(settings.database_url)
    app.state.delivery = LocalDiscardDelivery(settings.environment)
    try:
        yield
    finally:
        app.state.engine.dispose()


def create_app():
    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    app.include_router(ops_router)
    app.include_router(inventory_router)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # The default validation response echoes input, including OTP codes.
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request, error):
        return JSONResponse({"detail": "Service unavailable"}, status_code=503)

    @app.middleware("http")
    async def correlate_request(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        allowed_origins = {"http://localhost:8000", "http://127.0.0.1:8000"}
        if app.state.settings.environment == "test":
            allowed_origins.add("http://testserver")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and (
            request.headers.get("origin") not in allowed_origins | {None}
            or request.headers.get("sec-fetch-site") == "cross-site"
            or request.headers.get("content-type", "").split(";")[0]
            != "application/json"
        ):
            response = JSONResponse({"detail": "Request not allowed"}, status_code=403)
        else:
            try:
                response = await call_next(request)
            except Exception:
                # DB/provider exceptions can contain secrets: never log their text.
                response = JSONResponse(
                    {"detail": "Internal server error"}, status_code=500
                )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        logger.info("request_id=%s status=%s", request_id, response.status_code)
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
