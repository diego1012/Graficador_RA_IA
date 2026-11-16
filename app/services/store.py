"""Thread-safe in-memory dataset store with TTL and LRU eviction."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import RLock

from app.config import DATASET_TTL_SECONDS, MAX_DATASETS
from app.models.schemas import DatasetMetadata, TimeInfo, VariableInfo
from app.services.cleaning import CleanedDataset
from app.services.errors import AppError
from app.services.palette import assign_colors


@dataclass
class StoredDataset:
    dataset_id: str
    filename: str
    cleaned: CleanedDataset
    metadata: DatasetMetadata
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)


def build_metadata(
    cleaned: CleanedDataset,
    dataset_id: str,
    filename: str,
) -> DatasetMetadata:
    colors = assign_colors(cleaned.columns)
    variables: list[VariableInfo] = []

    for variable_id, column in cleaned.variable_ids.items():
        series = cleaned.frame[column]
        variables.append(
            VariableInfo(
                id=variable_id,
                name=column,
                color=colors[column],
                min=float(series.min()),
                max=float(series.max()),
                is_constant=bool(series.nunique(dropna=True) <= 1),
            )
        )

    if cleaned.time_kind == "datetime":
        time_values: list[str | float] = [
            timestamp.isoformat(sep=" ", timespec="milliseconds")
            for timestamp in cleaned.frame.index
        ]
    else:
        time_values = [round(float(value), 9) for value in cleaned.frame.index]

    time_info = TimeInfo(
        kind=cleaned.time_kind,
        origin=cleaned.time_origin,
        start=time_values[0],
        end=time_values[-1],
        label=cleaned.time_label,
        sample_interval_s=cleaned.sample_interval_s,
        values=time_values,
    )

    return DatasetMetadata(
        dataset_id=dataset_id,
        filename=filename,
        format=cleaned.format_name,
        rows_raw=cleaned.rows_raw,
        rows_clean=cleaned.rows_clean,
        dropped_rows_empty=cleaned.dropped_rows_empty,
        dropped_rows_invalid_time=cleaned.dropped_rows_invalid_time,
        dropped_rows_null=cleaned.dropped_rows_null,
        dropped_columns_empty=cleaned.dropped_columns_empty,
        dropped_columns_string=cleaned.dropped_columns_string,
        time=time_info,
        variables=variables,
    )


class DatasetStore:
    def __init__(
        self,
        ttl_seconds: int = DATASET_TTL_SECONDS,
        max_datasets: int = MAX_DATASETS,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_datasets = max_datasets
        self._items: dict[str, StoredDataset] = {}
        self._lock = RLock()

    def _purge_expired(self) -> None:
        now = time.time()
        expired = [
            dataset_id
            for dataset_id, item in self._items.items()
            if now - item.last_access > self._ttl_seconds
        ]
        for dataset_id in expired:
            del self._items[dataset_id]

    def put(self, filename: str, cleaned: CleanedDataset) -> DatasetMetadata:
        with self._lock:
            self._purge_expired()
            if len(self._items) >= self._max_datasets:
                oldest = min(
                    self._items,
                    key=lambda dataset_id: self._items[dataset_id].last_access,
                )
                del self._items[oldest]

            dataset_id = str(uuid.uuid4())
            metadata = build_metadata(cleaned, dataset_id, filename)
            self._items[dataset_id] = StoredDataset(
                dataset_id=dataset_id,
                filename=filename,
                cleaned=cleaned,
                metadata=metadata,
            )
            return metadata

    def get(self, dataset_id: str) -> StoredDataset:
        with self._lock:
            self._purge_expired()
            item = self._items.get(dataset_id)
            if item is None:
                raise AppError(
                    "DATASET_NOT_FOUND",
                    "El dataset no existe o expiró. Vuelve a cargar el archivo.",
                    404,
                    {"dataset_id": dataset_id},
                )
            item.last_access = time.time()
            return item

    def delete(self, dataset_id: str) -> None:
        with self._lock:
            if dataset_id not in self._items:
                raise AppError(
                    "DATASET_NOT_FOUND",
                    "El dataset no existe o expiró. Vuelve a cargar el archivo.",
                    404,
                    {"dataset_id": dataset_id},
                )
            del self._items[dataset_id]

    def count(self) -> int:
        with self._lock:
            self._purge_expired()
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


store = DatasetStore()
