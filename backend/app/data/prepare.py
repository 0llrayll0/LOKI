"""Preparação: limpeza opcional + splits treino/validação/teste — FASE 2.

Garantias:
- Opera sempre sobre CÓPIA do dataframe recebido (o original nunca é modificado);
- splits gravados em `{output_dir}/{train,val,test}.parquet` + `manifest.json`
  (nada é sobrescrito: se já existe, DataError — arquivos imutáveis);
- toda etapa aplicada é registrada em `transformations` e o resumo dos splits
  em `splits` (prontos para a coluna JSON da DatasetVersion).

Parâmetros:
- `strategy="random"`: embaralha com a seed fixa `SEED = 42` (reprodutível:
  mesma entrada + mesma seed → mesmo split) e corta por posição;
- `strategy="temporal"`: exige `time_col`, converte para datetime (erro se não
  converter), ordena de forma estável e NÃO embaralha — os splits são cortes
  posicionais preservando a ordem cronológica;
- `ratios` default (0.7, 0.15, 0.15); corte = floor(n * ratio + 1e-9) para
  train e val (epsilon evita erro de ponto flutuante), o resto vai para test;
- `missing="drop"` remove linhas com qualquer nulo; `"mean"`/`"median"`
  preenchem apenas colunas numéricas (não-numéricas permanecem nulas);
  `"ffill"` propaga o valor anterior de qualquer coluna; `"none"` não altera;
- `outliers="clip"` limita colunas numéricas aos limites IQR de
  `detect_outliers` (ordem das etapas: missing → outliers → split);
- `target` informado: coluna com valores/dtype idênticos ao target → DataError
  (vazamento); coluna única por linha (id-like) é sinalizada em `leakage_flags`
  como candidata — recusa automática só para a idêntica ao alvo.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.data.errors import DataError
from app.data.outliers import detect_outliers

SEED = 42
RATIOS_DEFAULT = (0.7, 0.15, 0.15)
_STRATEGIES = ("random", "temporal")
_MISSING = ("drop", "mean", "median", "ffill", "none")
_OUTLIERS = ("keep", "clip")
_SPLIT_FILES = ("train", "val", "test")


@dataclass(frozen=True)
class PrepareResult:
    """Etapas aplicadas, manifesto dos splits e flags de vazamento."""

    transformations: list[dict]
    splits: dict
    split_paths: dict[str, str]
    leakage_flags: list[str]


def _check_params(
    df: pd.DataFrame,
    *,
    target: str | None,
    strategy: str,
    time_col: str | None,
    ratios: tuple[float, float, float],
    missing: str,
    outliers: str,
) -> None:
    if strategy not in _STRATEGIES:
        raise DataError(f"strategy inválida: {strategy!r} (use 'random' ou 'temporal')")
    if missing not in _MISSING:
        raise DataError(f"missing inválida: {missing!r} (use {', '.join(_MISSING)})")
    if outliers not in _OUTLIERS:
        raise DataError(f"outliers inválida: {outliers!r} (use 'keep' ou 'clip')")
    if len(ratios) != 3 or any(r <= 0 for r in ratios) or abs(sum(ratios) - 1.0) > 1e-6:
        raise DataError(f"ratios inválidos: {ratios!r} (3 valores > 0 somando 1.0)")
    if len(df) < 2:
        raise DataError("prepare requer pelo menos 2 linhas")
    if target is not None and target not in df.columns:
        raise DataError(f"target '{target}' não existe nas colunas do dataset")
    if strategy == "temporal" and time_col is None:
        raise DataError("strategy 'temporal' exige informar time_col (coluna datetime)")
    if strategy == "temporal" and time_col is not None and time_col not in df.columns:
        raise DataError(f"time_col '{time_col}' não existe nas colunas do dataset")


def _leakage_flags(df: pd.DataFrame, target: str | None) -> list[str]:
    """Recusa coluna idêntica ao target; sinaliza ids únicos por linha."""
    flags: list[str] = []
    if target is None:
        return flags
    target_series = df[target]
    for i in range(df.shape[1]):
        name = df.columns[i]
        if name == target:
            continue
        series = df.iloc[:, i]
        if series.equals(target_series):
            raise DataError(
                f"vazamento: coluna '{name}' é idêntica ao target '{target}' "
                "— remova-a ou troque o target antes do prepare"
            )
        if len(df) > 1 and series.notna().all() and series.nunique() == len(df):
            flags.append(str(name))
    return flags


def _apply_missing(data: pd.DataFrame, missing: str, transformations: list[dict]) -> pd.DataFrame:
    """Aplica a estratégia de nulos; retorna o frame tratado e registra a etapa."""
    if missing == "drop":
        before = len(data)
        data = data.dropna().reset_index(drop=True)
        if len(data) < 2:
            raise DataError(
                f"missing='drop' removeu linhas demais: restam {len(data)} (mínimo 2)"
            )
        transformations.append(
            {"step": "missing", "strategy": "drop", "dropped_rows": before - len(data)}
        )
        return data
    if missing in ("mean", "median"):
        filled: dict[str, float] = {}
        for col in data.select_dtypes(include="number").columns:
            if data[col].isna().any():
                value = getattr(data[col], missing)()
                number = float(value) if pd.notna(value) else None
                if number is None:
                    continue  # coluna 100% nula: sem valor para preencher
                data[col] = data[col].fillna(number)
                filled[str(col)] = number
        transformations.append({"step": "missing", "strategy": missing, "filled": filled})
        return data
    if missing == "ffill":
        data = data.ffill()
        transformations.append({"step": "missing", "strategy": "ffill"})
        return data
    transformations.append({"step": "missing", "strategy": "none"})
    return data


def _apply_outliers(data: pd.DataFrame, outliers: str, transformations: list[dict]) -> pd.DataFrame:
    """Clip IQR (se pedido) no frame tratado; retorna o frame e registra a etapa."""
    if outliers == "keep":
        transformations.append({"step": "outliers", "action": "keep"})
        return data
    clipped: dict[str, int] = {}
    for col, info in detect_outliers(data).items():
        if info["outliers"] == 0 or col not in data.columns:
            continue
        data[col] = data[col].clip(lower=float(info["lower"]), upper=float(info["upper"]))
        clipped[col] = int(info["outliers"])
    transformations.append({"step": "outliers", "action": "clip", "clipped": clipped})
    return data


def _split(
    data: pd.DataFrame, strategy: str, time_col: str | None, ratios: tuple, seed: int
) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    """Embaralha (random) ou ordena por tempo (temporal) e corta os 3 splits."""
    transformations: list[dict] = []
    if strategy == "random":
        data = data.sample(frac=1, random_state=seed).reset_index(drop=True)
        transformations.append({"step": "shuffle", "strategy": "random", "seed": seed})
    else:
        assert time_col is not None  # validado em _check_params
        try:
            data[time_col] = pd.to_datetime(data[time_col], errors="raise")
        except (ValueError, TypeError) as exc:
            raise DataError(
                f"coluna temporal '{time_col}' não é conversível para datetime: {exc}"
            ) from exc
        data = data.sort_values(time_col, kind="stable").reset_index(drop=True)
        transformations.append(
            {"step": "order", "strategy": "temporal", "time_col": time_col, "shuffled": False}
        )
    n = len(data)
    n_train = min(n, int(n * ratios[0] + 1e-9))
    n_val = min(n - n_train, int(n * ratios[1] + 1e-9))
    splits = {
        "train": data.iloc[:n_train],
        "val": data.iloc[n_train : n_train + n_val],
        "test": data.iloc[n_train + n_val :],
    }
    return splits, transformations


def prepare(
    df: pd.DataFrame,
    *,
    output_dir: str | Path,
    target: str | None = None,
    strategy: str = "random",
    time_col: str | None = None,
    ratios: tuple[float, float, float] = RATIOS_DEFAULT,
    seed: int = SEED,
    missing: str = "none",
    outliers: str = "keep",
) -> PrepareResult:
    """Valida parâmetros, limpe opcionalmente (sobre cópia) e grava os splits."""
    _check_params(
        df,
        target=target,
        strategy=strategy,
        time_col=time_col,
        ratios=ratios,
        missing=missing,
        outliers=outliers,
    )
    leakage_flags = _leakage_flags(df, target)

    data = df.copy(deep=True)  # CÓPIA: o original não é alterado
    transformations: list[dict] = []
    data = _apply_missing(data, missing, transformations)
    data = _apply_outliers(data, outliers, transformations)
    parts, split_steps = _split(data, strategy, time_col, ratios, seed)
    transformations.extend(split_steps)

    out = Path(output_dir)
    existing = [
        name
        for name in (*_SPLIT_FILES, "manifest.json")
        if (out / name).exists()
    ]
    if existing:
        raise DataError(f"splits já existem em '{out}' (imutável): {', '.join(existing)}")
    try:
        out.mkdir(parents=True, exist_ok=True)
        for name in _SPLIT_FILES:
            parts[name].to_parquet(out / f"{name}.parquet", index=False, engine="pyarrow")
    except OSError as exc:
        raise DataError(f"falha ao gravar splits em '{out}': {exc}") from exc

    rows = {name: int(len(parts[name])) for name in _SPLIT_FILES}
    splits: dict = {
        "strategy": strategy,
        "seed": seed,
        "ratios": list(ratios),
        "target": target,
        "time_col": time_col,
        "missing": missing,
        "outliers": outliers,
        "total_rows": int(len(data)),
        "splits": {
            name: {"file": f"{name}.parquet", "rows": rows[name]} for name in _SPLIT_FILES
        },
    }
    transformations.append({"step": "split", "ratios": list(ratios), "rows": rows})
    try:
        with open(out / "manifest.json", "w", encoding="utf-8") as fh:
            json.dump(splits, fh, indent=2, ensure_ascii=False, allow_nan=False)
    except OSError as exc:
        raise DataError(f"falha ao gravar manifest em '{out}': {exc}") from exc

    split_paths = {name: str(out / f"{name}.parquet") for name in _SPLIT_FILES}
    split_paths["manifest"] = str(out / "manifest.json")
    return PrepareResult(
        transformations=transformations,
        splits=splits,
        split_paths=split_paths,
        leakage_flags=leakage_flags,
    )
