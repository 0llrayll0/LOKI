"""Detecção de outliers pelo método IQR de Tukey — reporta, NUNCA remove.

Por coluna numérica (exceto bool): limites `q1 - 1.5*IQR` e `q3 + 1.5*IQR`,
contagem e percentual de valores fora dos limites. A remoção/clipping é uma
decisão do `prepare` (parâmetro `outliers: keep|clip`), nunca automática aqui.
"""

import pandas as pd


def detect_outliers(df: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    """Contagem de outliers IQR por coluna numérica (colunas não-numéricas: fora)."""
    result: dict[str, dict[str, float | int]] = {}
    for i in range(df.shape[1]):
        series = df.iloc[:, i]
        if not pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
            continue
        valid = series.dropna()
        if valid.empty:
            continue
        q1 = float(valid.quantile(0.25))
        q3 = float(valid.quantile(0.75))
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        count = int(((valid < lower) | (valid > upper)).sum())
        result[str(df.columns[i])] = {
            "q1": q1,
            "q3": q3,
            "iqr": iqr,
            "lower": lower,
            "upper": upper,
            "outliers": count,
            "pct": round(100 * count / len(valid), 2),
        }
    return result
