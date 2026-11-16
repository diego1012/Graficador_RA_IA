"""FastAPI application entrypoint."""

from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.api.routes import router
from app.config import APP_VERSION, LOG_LEVEL
from app.services.errors import AppError

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
_asset_hashes: dict[str, tuple[int, str]] = {}


def asset_url(path: str) -> str:
    """Static URL with a content fingerprint (``?v=``) for cache busting.

    A changed file gets a new URL, so a browser can never pair a fresh page
    with a stale cached script or stylesheet. Hashes are cached per mtime.
    """
    relative = path.lstrip("/")
    file_path = (STATIC_DIR / relative).resolve()
    if not file_path.is_relative_to(STATIC_DIR.resolve()) or not file_path.is_file():
        raise ValueError(f"Unknown static asset: {path}")
    mtime = file_path.stat().st_mtime_ns
    cached = _asset_hashes.get(relative)
    if cached is None or cached[0] != mtime:
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()[:12]
        cached = (mtime, digest)
        _asset_hashes[relative] = cached
    return f"/static/{relative}?v={cached[1]}"


templates.env.globals["asset_url"] = asset_url


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    yield


app = FastAPI(
    title="Graficador Rockwell",
    version=APP_VERSION,
    description="Carga, limpieza y graficación interactiva de CSV eléctricos Rockwell.",
    lifespan=lifespan,
)
app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)
app.include_router(router)


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "code": exc.code,
                "message": exc.message,
                "context": exc.context,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    _: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    errors = exc.errors()
    fields = " ".join(str(error.get("loc", "")) for error in errors).lower()
    details = " ".join(str(error.get("msg", "")) for error in errors).lower()
    if "color" in fields or "color" in details:
        code = "INVALID_COLOR"
        message = "El color debe tener el formato #RRGGBB."
    elif any("scale" in error.get("loc", ()) for error in errors):
        code = "VALIDATION_ERROR"
        message = "El escalado requiere un mínimo menor que el máximo, ambos numéricos."
    elif any(error.get("loc", ())[-1:] in (("name",), ("unit",)) for error in errors):
        code = "VALIDATION_ERROR"
        message = (
            "El nombre de la variable admite hasta 80 caracteres y la unidad hasta 4 caracteres."
        )
    elif "range" in fields or "end_index" in details:
        code = "INVALID_RANGE"
        message = "El rango seleccionado no es válido."
    elif "variables" in fields or "variable" in details:
        code = "INVALID_VARIABLE"
        message = "La selección de variables no es válida."
    else:
        code = "VALIDATION_ERROR"
        message = "La solicitud no es válida."

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": code,
                "message": message,
                "context": {"errors": jsonable_encoder(errors)},
            }
        },
    )


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    path = request.url.path
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif path == "/" or path.startswith("/static/"):
        # Always revalidate (cheap 304 via ETag) so the browser never pairs a
        # fresh page with a stale app.js after an update.
        response.headers["Cache-Control"] = "no-cache"
    return response
