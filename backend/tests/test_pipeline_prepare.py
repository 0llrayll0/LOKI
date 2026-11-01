"""Testes do prepare: splits, limpeza, temporal e vazamento — FASE 2."""

import json
from pathlib import Path

import pandas as pd
import pytest

from app.data import DataError, prepare


def _df(n: int = 100) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": list(range(n)),
            "valor": [float(i % 10) for i in range(n)],  # repetido: não é id único
            "grupo": ["a" if i % 3 else "b" for i in range(n)],
            "y": [i % 2 for i in range(n)],
        }
    )


def _combined(out: Path) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(out / f"{name}.parquet") for name in ("train", "val", "test")],
        ignore_index=True,
    )


def test_random_split_ok(tmp_path):
    df = _df(100)
    original = df.copy(deep=True)
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out)

    assert df.equals(original)  # opera só sobre cópia: original intacto
    for name, rows in (("train", 70), ("val", 15), ("test", 15)):
        assert len(pd.read_parquet(out / f"{name}.parquet")) == rows
    combined = _combined(out)
    assert sorted(combined["id"]) == list(range(100))  # sem perda nem duplicata

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == result.splits
    assert manifest["strategy"] == "random" and manifest["seed"] == 42
    assert manifest["ratios"] == [0.7, 0.15, 0.15]
    assert manifest["splits"]["train"] == {"file": "train.parquet", "rows": 70}
    assert manifest["total_rows"] == 100
    assert set(result.split_paths) == {"train", "val", "test", "manifest"}

    steps = [t["step"] for t in result.transformations]
    assert steps == ["missing", "outliers", "shuffle", "split"]
    assert next(t for t in result.transformations if t["step"] == "shuffle")["seed"] == 42
    assert result.leakage_flags == []


def test_seed_fixa_reprodutivel(tmp_path):
    df = _df(50)
    prepare(df, output_dir=tmp_path / "a")
    prepare(df, output_dir=tmp_path / "b")
    train_a = pd.read_parquet(tmp_path / "a" / "train.parquet")
    train_b = pd.read_parquet(tmp_path / "b" / "train.parquet")
    assert list(train_a["id"]) == list(train_b["id"])  # mesma seed → mesmo split


def test_splits_ja_existem_sao_imutaveis(tmp_path):
    df = _df(10)
    out = tmp_path / "splits"
    prepare(df, output_dir=out)
    with pytest.raises(DataError, match="já existem"):
        prepare(df, output_dir=out)


# ------------------------------------------------------------------ temporal ---


def test_temporal_preserva_ordem_sem_embaralhar(tmp_path):
    n = 20
    times = pd.date_range("2026-01-01", periods=n, freq="D")
    df = pd.DataFrame({"t": times, "id": list(range(n)), "y": [i % 2 for i in range(n)]})
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, strategy="temporal", time_col="t")

    # cortes posicionais cronológicos: 14 / 3 / 3, na ordem original
    assert list(pd.read_parquet(out / "train.parquet")["id"]) == list(range(14))
    assert list(pd.read_parquet(out / "val.parquet")["id"]) == [14, 15, 16]
    assert list(pd.read_parquet(out / "test.parquet")["id"]) == [17, 18, 19]
    steps = [t["step"] for t in result.transformations]
    assert "shuffle" not in steps and "order" in steps
    order = next(t for t in result.transformations if t["step"] == "order")
    assert order["shuffled"] is False


def test_temporal_entrada_desordenada_fica_cronologica(tmp_path):
    n = 12
    times = pd.date_range("2026-01-01", periods=n, freq="D")
    df = pd.DataFrame({"t": times, "id": list(range(n))})
    desordenado = df.sample(frac=1, random_state=7).reset_index(drop=True)
    out = tmp_path / "splits"

    prepare(desordenado, output_dir=out, strategy="temporal", time_col="t")

    combined = _combined(out)
    assert combined["t"].is_monotonic_increasing  # ordena pelo tempo (estável)
    assert list(combined["id"]) == list(range(n))  # nada perdido no corte


def test_temporal_exige_time_col(tmp_path):
    with pytest.raises(DataError, match="time_col"):
        prepare(_df(10), output_dir=tmp_path / "s", strategy="temporal")


def test_temporal_coluna_nao_conversivel(tmp_path):
    with pytest.raises(DataError, match="datetime"):
        prepare(
            _df(10),
            output_dir=tmp_path / "s",
            strategy="temporal",
            time_col="grupo",  # strings "a"/"b" não são datas
        )


# ------------------------------------------------------------------ missing ---


def test_missing_median_preenche_so_numericos(tmp_path):
    df = pd.DataFrame(
        {"a": [1.0, 2.0, 3.0, 4.0, None], "b": ["x", "y", "z", "w", None], "y": [0, 1, 0, 1, 0]}
    )
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, missing="median")

    combined = _combined(out)
    assert len(combined) == 5
    assert combined["a"].isna().sum() == 0
    assert (combined["a"] == 2.5).sum() == 1  # nulo virou a mediana
    assert combined["b"].isna().sum() == 1  # não-numérico: não mente, não preenche
    step = next(t for t in result.transformations if t["step"] == "missing")
    assert step["strategy"] == "median" and step["filled"] == {"a": 2.5}


def test_missing_drop_remove_linhas_e_registra(tmp_path):
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, None], "y": [0, 1, 0, 1]})
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, missing="drop")

    assert len(_combined(out)) == 3
    step = next(t for t in result.transformations if t["step"] == "missing")
    assert step == {"step": "missing", "strategy": "drop", "dropped_rows": 1}


def test_missing_ffill_propaga(tmp_path):
    df = pd.DataFrame({"a": [1.0, None, 3.0, 4.0], "b": ["x", "y", None, "w"]})
    out = tmp_path / "splits"

    prepare(df, output_dir=out, missing="ffill")

    combined = _combined(out)
    assert len(combined) == 4
    assert combined["a"].isna().sum() == 0 and combined["b"].isna().sum() == 0


def test_missing_none_preserva_nulos(tmp_path):
    df = pd.DataFrame({"a": [1.0, None, 3.0, 4.0], "y": [0, 1, 0, 1]})
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, missing="none")

    assert _combined(out)["a"].isna().sum() == 1  # nulo honesto, sem fingir
    step = next(t for t in result.transformations if t["step"] == "missing")
    assert step["strategy"] == "none"


# ----------------------------------------------------------------- outliers ---


def test_outliers_clip_corta_nos_limites_iqr(tmp_path):
    df = pd.DataFrame({"id": list(range(10)), "sinal": [0.0] * 9 + [10.0], "y": [0, 1] * 5})
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, outliers="clip")

    assert _combined(out)["sinal"].max() == 0.0  # 10 > upper IQR (0) → cortado
    step = next(t for t in result.transformations if t["step"] == "outliers")
    assert step["action"] == "clip" and step["clipped"] == {"sinal": 1}


def test_outliers_keep_nao_altera(tmp_path):
    df = pd.DataFrame({"id": list(range(10)), "sinal": [0.0] * 9 + [10.0], "y": [0, 1] * 5})
    out = tmp_path / "splits"

    result = prepare(df, output_dir=out, outliers="keep")

    assert _combined(out)["sinal"].max() == 10.0  # reporta, não remove
    step = next(t for t in result.transformations if t["step"] == "outliers")
    assert step["action"] == "keep"


# ---------------------------------------------------------------- vazamento ---


def test_vazamento_coluna_identica_ao_target_recusa(tmp_path):
    df = _df(20)
    df["leak"] = df["y"]  # idêntica ao target

    with pytest.raises(DataError, match="vazamento"):
        prepare(df, output_dir=tmp_path / "s", target="y")


def test_vazamento_flags_id_unico_por_linha(tmp_path):
    df = _df(20)

    result = prepare(df, output_dir=tmp_path / "s", target="y")

    assert result.leakage_flags == ["id"]  # só o id é único por linha
    assert result.splits["target"] == "y"


# ------------------------------------------------------------ parâmetros ---


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"strategy": "zigzag"}, "strategy inválida"),
        ({"missing": "magic"}, "missing inválida"),
        ({"outliers": "delete"}, "outliers inválida"),
        ({"ratios": (0.5, 0.5)}, "ratios"),
        ({"ratios": (0.8, 0.2, 0.1)}, "ratios"),
        ({"target": "nao_existe"}, "não existe"),
    ],
)
def test_parametros_invalidos_recusados(tmp_path, kwargs, match):
    with pytest.raises(DataError, match=match):
        prepare(_df(10), output_dir=tmp_path / "s", **kwargs)


def test_prepare_requer_minimo_dois_linhas(tmp_path):
    with pytest.raises(DataError, match="2 linhas"):
        prepare(pd.DataFrame({"a": [1], "y": [0]}), output_dir=tmp_path / "s")
