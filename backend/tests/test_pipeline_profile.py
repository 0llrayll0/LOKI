"""Testes do profiling e da detecção de outliers — FASE 2 (dataframes sintéticos)."""

import json
import math

import pandas as pd
import pytest

from app.data import detect_outliers, profile_dataset


def test_profile_dataset_estrutura_e_nota():
    df = pd.DataFrame(
        {
            "num": [1.0, 2.0, 3.0, 4.0, None],
            "cat": ["a", "b", "a", "a", None],
            "const": [7, 7, 7, 7, 7],
            "id": [10, 11, 12, 13, 14],
        }
    )

    profile = profile_dataset(df)

    assert profile["rows"] == 5 and profile["cols"] == 4
    assert profile["null_cells"] == 2
    assert profile["duplicated_rows"] == 0
    assert profile["memory_bytes"] > 0
    # fórmula do docstring: 100 * (1 - 2/20) * (1 - 0/5) = 90.0
    assert profile["quality_score"] == 90.0
    json.dumps(profile)  # perfil inteiro é JSON-safe (NaN → null)

    by_name = {c["name"]: c for c in profile["columns"]}
    num = by_name["num"]
    assert num["dtype"].startswith("float")
    assert num["non_null"] == 4 and num["null_pct"] == 20.0 and num["unique"] == 4
    assert num["mean"] == pytest.approx(2.5)
    assert num["median"] == pytest.approx(2.5)
    assert num["q1"] == pytest.approx(1.75) and num["q3"] == pytest.approx(3.25)
    assert num["min"] == 1.0 and num["max"] == 4.0
    assert num["std"] is not None

    cat = by_name["cat"]
    assert cat["top5"][0] == {"value": "a", "count": 3}
    assert "mean" not in cat

    assert "constante" in by_name["const"]["flags"]
    assert "vazamento_candidato" in by_name["id"]["flags"]
    assert by_name["num"]["flags"] == []


def test_flag_quase_constante():
    df = pd.DataFrame({"flag": ["x"] * 995 + ["y"] * 5, "id": range(1000)})

    profile = profile_dataset(df)
    column = profile["columns"][0]

    assert "quase_constante" in column["flags"]  # 99,5% igual > 99%
    assert "constante" not in column["flags"]  # mas não é constante de verdade
    assert profile["quality_score"] == 100.0  # sem nulos e sem linhas duplicadas


def test_coluna_totalmente_nula_e_json_safe():
    df = pd.DataFrame({"a": [math.nan] * 4, "b": [1.0, 2.0, math.nan, 4.0]})

    profile = profile_dataset(df)

    col_a = profile["columns"][0]
    assert col_a["null_pct"] == 100.0
    assert col_a["mean"] is None and col_a["min"] is None  # NaN vira null
    assert col_a["flags"] == []
    json.dumps(profile)


def test_linhas_duplicadas_na_nota():
    df = pd.DataFrame({"a": [1, 1, 2, 2], "b": ["x", "x", "y", "y"]})

    profile = profile_dataset(df)

    assert profile["duplicated_rows"] == 2
    # 100 * (1 - 0) * (1 - 2/4) = 50.0
    assert profile["quality_score"] == 50.0


def test_outliers_iqr_conta_sem_remover():
    df = pd.DataFrame(
        {
            "sinal": [0.0] * 9 + [10.0],
            "ok": [float(i) for i in range(1, 11)],
            "txt": list("abcdefghij"),
            "bool": [True, False] * 5,
            "vazio_num": [math.nan] * 10,
        }
    )
    antes = df.copy(deep=True)

    result = detect_outliers(df)

    assert df.equals(antes)  # só reporta: nada é removido/alterado
    assert set(result) == {"sinal", "ok"}  # numéricas de verdade; não bool/txt/nulo
    assert result["sinal"]["outliers"] == 1
    assert result["sinal"]["lower"] == 0.0 and result["sinal"]["upper"] == 0.0
    assert result["sinal"]["pct"] == 10.0
    assert result["ok"]["outliers"] == 0
