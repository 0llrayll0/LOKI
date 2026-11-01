"""Testes da ingestão e validação do pipeline — FASE 2 (arquivos sintéticos)."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.config import Settings
from app.data import DataError, detect_format, ingest, validate_dataframe


def _df(n: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": list(range(n)),
            "valor": [float(i) + 0.5 for i in range(n)],
            "grupo": ["par" if i % 2 == 0 else "impar" for i in range(n)],
        }
    )


def _ingest(source: Path, tmp_path: Path, **kwargs):
    return ingest(
        source,
        dataset_id=kwargs.pop("dataset_id", "ds1"),
        version=kwargs.pop("version", 1),
        datasets_dir=kwargs.pop("datasets_dir", tmp_path / "store"),
        max_upload_mb=kwargs.pop("max_upload_mb", 10),
        **kwargs,
    )


# ---------------------------------------------------------------- settings ---


def test_settings_novos_defaults(monkeypatch):
    monkeypatch.delenv("LOKI_DATASETS_DIR", raising=False)
    monkeypatch.delenv("LOKI_MAX_UPLOAD_MB", raising=False)
    settings = Settings(_env_file=None)
    assert settings.datasets_dir == "./datasets"
    assert settings.max_upload_mb == 100


# ----------------------------------------------------------------- caminhos ok ---


def test_csv_ok_copia_imutavel_e_sha256(tmp_path):
    src = tmp_path / "dados.csv"
    _df().to_csv(src, index=False)
    original = src.read_bytes()

    result = _ingest(src, tmp_path)

    assert result.format == "csv"
    assert result.rows == 10 and result.cols == 3
    stored = tmp_path / "store" / "ds1" / "v1" / "original.csv"
    assert result.path == str(stored)
    assert stored.exists()
    assert src.read_bytes() == original  # original nunca modificado
    assert result.sha256 == hashlib.sha256(original).hexdigest()
    assert list(result.dataframe.columns) == ["id", "valor", "grupo"]


def test_csv_separador_ponto_e_virgula_e_latin1(tmp_path):
    conteudo = "nome;valor\nJosé;1.5\nAna;2.5\nMaria;3.5\n".encode("latin-1")
    src = tmp_path / "nomes.csv"
    src.write_bytes(conteudo)

    result = _ingest(src, tmp_path)

    assert result.cols == 2
    assert "José" in set(result.dataframe["nome"])


def test_json_records(tmp_path):
    src = tmp_path / "dados.json"
    _df().to_json(src, orient="records")

    result = _ingest(src, tmp_path)

    assert result.format == "json"
    assert result.rows == 10 and result.cols == 3


def test_json_lines_por_alias(tmp_path):
    linhas = "\n".join(json.dumps({"id": i, "valor": float(i)}) for i in range(6))
    src = tmp_path / "dados.jsonl"
    src.write_text(linhas, encoding="utf-8")

    result = _ingest(src, tmp_path)

    assert result.format == "json"
    assert result.rows == 6 and result.cols == 2


def test_xlsx(tmp_path):
    src = tmp_path / "dados.xlsx"
    _df().to_excel(src, index=False)

    result = _ingest(src, tmp_path)

    assert result.format == "xlsx"
    assert result.rows == 10 and result.cols == 3


def test_parquet(tmp_path):
    src = tmp_path / "dados.parquet"
    _df().to_parquet(src)

    result = _ingest(src, tmp_path)

    assert result.format == "parquet"
    assert result.rows == 10 and result.cols == 3


# --------------------------------------------------------- detecção/limites ---


def test_detect_format_por_sniff(tmp_path):
    (tmp_path / "tabela.dat").write_text("x,y\n1,2\n3,4\n", encoding="utf-8")
    assert detect_format(tmp_path / "tabela.dat") == "csv"

    parquet = tmp_path / "bom.parquet"
    _df().to_parquet(parquet)
    (tmp_path / "arquivo.bin").write_bytes(parquet.read_bytes())
    assert detect_format(tmp_path / "arquivo.bin") == "parquet"

    (tmp_path / "registro.xyz").write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert detect_format(tmp_path / "registro.xyz") == "json"


def test_formato_nao_suportado(tmp_path):
    lixo = tmp_path / "dados.xyz"
    lixo.write_bytes(b"\x00\x01\x02\x03")
    with pytest.raises(DataError, match="formato não suportado"):
        _ingest(lixo, tmp_path)


def test_limite_de_upload(tmp_path):
    grande = tmp_path / "grande.csv"
    grande.write_bytes(b"id,valor\n" + b"1,2\n" * 400_000)  # ~1,6 MB
    with pytest.raises(DataError, match="limite"):
        _ingest(grande, tmp_path, max_upload_mb=1)


def test_arquivo_nao_encontrado(tmp_path):
    with pytest.raises(DataError, match="não encontrado"):
        _ingest(tmp_path / "nao_existe.csv", tmp_path)


def test_dataset_id_invalido(tmp_path):
    src = tmp_path / "dados.csv"
    _df().to_csv(src, index=False)
    with pytest.raises(DataError, match="dataset_id inválido"):
        _ingest(src, tmp_path, dataset_id="../fuga")


def test_version_invalida(tmp_path):
    src = tmp_path / "dados.csv"
    _df().to_csv(src, index=False)
    with pytest.raises(DataError, match="version inválida"):
        _ingest(src, tmp_path, version=0)


def test_destino_imutavel(tmp_path):
    src = tmp_path / "dados.csv"
    _df().to_csv(src, index=False)
    _ingest(src, tmp_path)
    with pytest.raises(DataError, match="imutável"):
        _ingest(src, tmp_path)


# ------------------------------------------------------------- validação ---


def test_validacao_ok(tmp_path):
    src = tmp_path / "dados.csv"
    _df().to_csv(src, index=False)
    result = _ingest(src, tmp_path)
    validate_dataframe(result.dataframe, raw_columns=result.raw_columns)  # não levanta


def test_arquivo_vazio(tmp_path):
    src = tmp_path / "vazio.csv"
    src.write_bytes(b"")
    with pytest.raises(DataError, match="vazio"):
        _ingest(src, tmp_path)


def test_so_cabecalho_e_vazio(tmp_path):
    src = tmp_path / "cabecalho.csv"
    src.write_text("id,valor\n", encoding="utf-8")
    result = _ingest(src, tmp_path)
    with pytest.raises(DataError, match="vazio"):
        validate_dataframe(result.dataframe, raw_columns=result.raw_columns)


def test_sem_colunas():
    with pytest.raises(DataError, match="sem colunas"):
        validate_dataframe(pd.DataFrame())


def test_apenas_uma_linha(tmp_path):
    src = tmp_path / "uma_linha.csv"
    src.write_text("id,valor\n1,2.5\n", encoding="utf-8")
    result = _ingest(src, tmp_path)
    with pytest.raises(DataError, match="apenas 1 linha"):
        validate_dataframe(result.dataframe, raw_columns=result.raw_columns)


def test_colunas_duplicadas_csv(tmp_path):
    src = tmp_path / "dup.csv"
    src.write_text("a,a,b\n1,2,3\n4,5,6\n", encoding="utf-8")
    result = _ingest(src, tmp_path)
    assert result.raw_columns == ["a", "a", "b"]  # cabeçalho cru preservado
    with pytest.raises(DataError, match="colunas duplicadas: a"):
        validate_dataframe(result.dataframe, raw_columns=result.raw_columns)


# ------------------------------------------------------------ corrompidos ---


def test_json_corrompido(tmp_path):
    src = tmp_path / "quebrado.json"
    src.write_text('{"aberto": ', encoding="utf-8")
    with pytest.raises(DataError, match="corrompido"):
        _ingest(src, tmp_path)


def test_parquet_truncado(tmp_path):
    bom = tmp_path / "bom.parquet"
    _df().to_parquet(bom)
    dados = bom.read_bytes()
    src = tmp_path / "truncado.parquet"
    src.write_bytes(dados[: len(dados) // 2])
    with pytest.raises(DataError, match="corrompido"):
        _ingest(src, tmp_path)


def test_xlsx_corrompido(tmp_path):
    src = tmp_path / "quebrado.xlsx"
    src.write_bytes(b"isto nao e um arquivo excel")
    with pytest.raises(DataError, match="corrompido"):
        _ingest(src, tmp_path)
