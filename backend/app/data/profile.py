"""Profiling de dataset e de colunas — FASE 2 (só relata, não altera dados).

Flags honestas por coluna:
- "constante": todos os valores não-nulos iguais (unique <= 1);
- "quase_constante": um único valor responde por mais de 99% dos não-nulos;
- "vazamento_candidato": valor único por linha (id por linha). A checagem de
  coluna idêntica ao target só é avaliável no `prepare`, que recusa o alvo
  duplicado com erro claro.

Nota de qualidade (quality_score) — derivada somente de nulos e duplicadas:

    null_ratio = células_nulas / (rows * cols)
    dup_ratio  = linhas_duplicadas / rows
    score      = round(100 * (1 - null_ratio) * (1 - dup_ratio), 1)

score = 0.0 quando rows*cols == 0. Quanto mais nulos e linhas duplicadas,
menor a nota (máximo 100.0 = sem nulos e sem duplicatas). Todos os valores
do perfil são JSON-safe (NaN/inf viram null).
"""

import math
from datetime import date, datetime, time
from typing import Any

import pandas as pd


def _is_numeric(series: pd.Series) -> bool:
    """Numérico de verdade (bool e datetime contam como categóricos aqui)."""
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def _json_float(value: object) -> float | None:
    """Float finito para JSON; NaN/inf/NA viram None."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _json_safe(value: object) -> Any:
    """Valor escalar JSON-safe (numpy → python, datetime → ISO, resto → str)."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def profile_column(name: str, series: pd.Series, *, total_rows: int) -> dict[str, Any]:
    """Perfil de uma coluna: dtype, nulos, únicos, stats numéricas ou top 5."""
    non_null = int(series.notna().sum())
    nulls = total_rows - non_null
    unique = int(series.nunique(dropna=True))
    column: dict[str, Any] = {
        "name": str(name),
        "dtype": str(series.dtype),
        "non_null": non_null,
        "null_pct": round(100 * nulls / total_rows, 2) if total_rows else 0.0,
        "unique": unique,
        "flags": [],
    }

    if _is_numeric(series):
        valid = series.dropna()
        column.update(
            {
                "mean": _json_float(valid.mean()),
                "std": _json_float(valid.std()),  # ddof=1
                "min": _json_float(valid.min()),
                "max": _json_float(valid.max()),
                "q1": _json_float(valid.quantile(0.25)),
                "median": _json_float(valid.quantile(0.5)),
                "q3": _json_float(valid.quantile(0.75)),
            }
        )
    else:
        counts = series.value_counts(dropna=True).head(5)
        column["top5"] = [
            {"value": _json_safe(value), "count": int(count)} for value, count in counts.items()
        ]

    flags: list[str] = column["flags"]
    if non_null:
        if unique <= 1:
            flags.append("constante")
        else:
            top_count = int(series.value_counts(dropna=True).iloc[0])
            if top_count / non_null > 0.99:
                flags.append("quase_constante")
        if unique == total_rows and total_rows > 1:
            flags.append("vazamento_candidato")
    return column


def profile_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Perfil do dataset: shapes, memória, duplicadas, nota e colunas.

    A nota (quality_score) segue a fórmula documentada no docstring do módulo.
    """
    rows, cols = int(df.shape[0]), int(df.shape[1])
    null_cells = int(df.isna().sum().sum())
    duplicated_rows = int(df.duplicated().sum())
    if rows > 0 and cols > 0:
        null_ratio = null_cells / (rows * cols)
        dup_ratio = duplicated_rows / rows
        quality_score = round(100 * (1 - null_ratio) * (1 - dup_ratio), 1)
    else:
        quality_score = 0.0
    return {
        "rows": rows,
        "cols": cols,
        "memory_bytes": int(df.memory_usage(deep=True).sum()),
        "null_cells": null_cells,
        "duplicated_rows": duplicated_rows,
        "quality_score": quality_score,
        "columns": [
            profile_column(str(df.columns[i]), df.iloc[:, i], total_rows=rows)
            for i in range(cols)
        ],
    }
