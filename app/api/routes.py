"""HTTP routes for upload, metadata, plotting and health."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Request, Response, UploadFile
from fastapi.responses import HTMLResponse

from app.config import APP_VERSION, MAX_UPLOAD_BYTES
from app.models.schemas import DatasetMetadata, PlotRequest, PlotResponse
from app.services.cleaning import clean_parsed
from app.services.errors import AppError
from app.services.ingest import parse_csv
from app.services.plotting import build_figure
from app.services.store import store

router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request) -> HTMLResponse:
    from app.main import templates

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_version": APP_VERSION},
    )


@router.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "datasets": store.count(),
    }


@router.post("/api/datasets", response_model=DatasetMetadata, status_code=201)
async def create_dataset(file: UploadFile = File(...)) -> DatasetMetadata:
    filename = Path(file.filename or "dataset.csv").name
    if not filename.lower().endswith(".csv"):
        raise AppError(
            "UNSUPPORTED_FORMAT",
            "Solo se aceptan archivos con extensión .csv.",
            400,
            {"filename": filename},
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise AppError(
            "FILE_TOO_LARGE",
            f"El archivo supera el máximo de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            413,
            {"bytes": len(raw), "max_bytes": MAX_UPLOAD_BYTES},
        )

    parsed = parse_csv(raw, filename)
    cleaned = clean_parsed(parsed)
    return store.put(filename, cleaned)


@router.get("/api/datasets/{dataset_id}", response_model=DatasetMetadata)
async def get_dataset(dataset_id: str) -> DatasetMetadata:
    return store.get(dataset_id).metadata


@router.post("/api/datasets/{dataset_id}/plot", response_model=PlotResponse)
async def plot_dataset(dataset_id: str, payload: PlotRequest) -> PlotResponse:
    return build_figure(store.get(dataset_id), payload)


@router.delete("/api/datasets/{dataset_id}", status_code=204)
async def delete_dataset(dataset_id: str) -> Response:
    store.delete(dataset_id)
    return Response(status_code=204)
