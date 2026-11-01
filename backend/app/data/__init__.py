"""Pipeline de dados da FASE 2: ingestão → validação → profiling → prepare."""

from app.data.errors import DataError
from app.data.ingest import IngestResult, detect_format, ingest
from app.data.outliers import detect_outliers
from app.data.prepare import PrepareResult, prepare
from app.data.profile import profile_column, profile_dataset
from app.data.validate import validate_columns, validate_dataframe

__all__ = [
    "DataError",
    "IngestResult",
    "PrepareResult",
    "detect_format",
    "detect_outliers",
    "ingest",
    "prepare",
    "profile_column",
    "profile_dataset",
    "validate_columns",
    "validate_dataframe",
]
