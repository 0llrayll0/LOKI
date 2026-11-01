"""Ingestão de arquivos — CSV, JSON, XLSX e Parquet (FASE 2).

O arquivo original NUNCA é modificado: o pipeline copia os bytes para
`{datasets_dir}/{dataset_id}/v{version}/original.{ext}` (destino imutável —
se já existe, erro) e calcula o sha256 do artefato copiado para rastreio na
DatasetVersion.

Formato: extensão conhecida primeiro (csv/json/xlsx/parquet + alias tsv, txt,
jsonl, ndjson); sem extensão reconhecida, sniff do conteúdo (PAR1 → parquet,
PK → xlsx, { ou [ → json, texto → csv; binário com NUL → formato não suportado).
CSV tenta separadores comuns (sniff + , ; tab |) e codificações (utf-8, latin-1).
"""

import csv
import hashlib
import shutil
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.data.errors import DataError

SUPPORTED_FORMATS = ("csv", "json", "xlsx", "parquet")
_EXTENSIONS_ALIASES = {"tsv": "csv", "txt": "csv", "jsonl": "json", "ndjson": "json"}
_CSV_SEPS = (",", ";", "\t", "|")
_ENCODINGS = ("utf-8", "latin-1")


@dataclass(frozen=True)
class IngestResult:
    """Arquivo lido, formato detectado, hash e cópia imutável gravada."""

    dataframe: pd.DataFrame
    filename: str
    format: str
    sha256: str
    size_bytes: int
    rows: int
    cols: int
    path: str
    raw_columns: list[str] | None = None


def detect_format(path: str | Path) -> str:
    """Detecta o formato: extensão conhecida (ou alias) primeiro, senão sniff."""
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    if ext in SUPPORTED_FORMATS:
        return ext
    if ext in _EXTENSIONS_ALIASES:
        return _EXTENSIONS_ALIASES[ext]
    with open(p, "rb") as fh:
        head = fh.read(4096)
    if not head:
        return "csv"  # vazio: o erro claro ("arquivo vazio") sai na leitura
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:]
    if head.startswith(b"PAR1"):
        return "parquet"
    if head.startswith(b"PK"):
        return "xlsx"
    if head.lstrip()[:1] in (b"{", b"["):
        return "json"
    if b"\x00" in head:
        raise DataError(
            f"formato não suportado: não foi possível identificar o conteúdo de '{p.name}'"
        )
    return "csv"


def _sniff_sep(path: Path) -> str | None:
    """Separação provável do CSV (csv.Sniffer numa amostra); None se falhar."""
    with open(path, "rb") as fh:
        sample = fh.read(65536)
    text = sample.decode("utf-8", errors="ignore")
    lines = text.splitlines()[:20]
    if not lines:
        return None
    try:
        return csv.Sniffer().sniff("\n".join(lines), delimiters=",;\t|").delimiter
    except csv.Error:
        return None


def _raw_header(path: Path, sep: str | None, encoding: str) -> list[str] | None:
    """Lê a primeira linha do CSV como está (antes do pandas renomear duplicatas)."""
    try:
        with open(path, encoding=encoding, newline="") as fh:
            line = fh.readline()
    except (OSError, UnicodeDecodeError):
        return None
    if not line:
        return None
    delimiter = sep or _sniff_sep(path) or ","
    try:
        return next(csv.reader([line], delimiter=delimiter))
    except csv.Error:
        return None


def _read_csv(path: Path) -> tuple[pd.DataFrame, list[str] | None]:
    """Lê CSV tentando separadores e codificações comuns; erro claro se corrompido."""
    sniffed = _sniff_sep(path)
    seps: list[str | None] = [sniffed] + [s for s in _CSV_SEPS if s != sniffed]
    last_error: Exception | None = None
    best: pd.DataFrame | None = None
    best_sep: str | None = sniffed
    best_encoding = _ENCODINGS[0]
    for encoding in _ENCODINGS:
        for sep in seps:
            try:
                df = pd.read_csv(
                    path,
                    sep=sep,
                    encoding=encoding,
                    engine="python" if sep is None else "c",
                )
            except pd.errors.EmptyDataError as exc:
                raise DataError(f"arquivo vazio: '{path.name}' não contém dados") from exc
            except UnicodeDecodeError as exc:
                last_error = exc
                break  # codificação errada: próxima codificação
            except (pd.errors.ParserError, csv.Error, UnicodeError, ValueError, OSError) as exc:
                last_error = exc
                continue
            if best is None or df.shape[1] > best.shape[1]:
                best, best_sep, best_encoding = df, sep, encoding
            if df.shape[1] > 1:
                return df, _raw_header(path, sep, encoding)
    if best is None:
        raise DataError(
            f"arquivo corrompido: não foi possível ler o CSV '{path.name}' ({last_error})"
        ) from last_error
    return best, _raw_header(path, best_sep, best_encoding)


def _read_json(path: Path) -> pd.DataFrame:
    """Lê JSON (array de objetos) ou JSON Lines; erro claro se corrompido."""
    raw = path.read_bytes()
    if not raw.strip():
        raise DataError(f"arquivo vazio: '{path.name}' não contém dados")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        return pd.read_json(StringIO(text), orient="records")
    except ValueError:
        pass
    try:
        return pd.read_json(StringIO(text), orient="records", lines=True)
    except ValueError as exc:
        raise DataError(
            f"arquivo corrompido: não foi possível ler o JSON '{path.name}' ({exc})"
        ) from exc


def _read(path: Path, fmt: str) -> tuple[pd.DataFrame, list[str] | None]:
    """Lê o arquivo no formato informado; qualquer falha de parser vira DataError."""
    try:
        if fmt == "csv":
            return _read_csv(path)
        if fmt == "json":
            return _read_json(path), None
        if fmt == "xlsx":
            return pd.read_excel(path, engine="openpyxl"), None
        if fmt == "parquet":
            return pd.read_parquet(path, engine="pyarrow"), None
    except DataError:
        raise
    except pd.errors.EmptyDataError as exc:
        raise DataError(f"arquivo vazio: '{path.name}' não contém dados") from exc
    except Exception as exc:  # qualquer falha de parser vira erro claro
        raise DataError(
            f"arquivo corrompido ou formato inválido ({fmt}): '{path.name}' "
            f"({type(exc).__name__})"
        ) from exc
    raise DataError(f"formato não suportado: {fmt!r}")


def _sha256(path: Path) -> str:
    """Hash sha256 do arquivo (stream de 1 MiB)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ingest(
    source: str | Path,
    *,
    dataset_id: str,
    version: int,
    datasets_dir: str | Path | None = None,
    max_upload_mb: int | None = None,
) -> IngestResult:
    """Lê `source`, aplica o limite de tamanho e grava a cópia imutável.

    Nunca modifica o arquivo original. Falhas claras (DataError): arquivo
    inexistente, acima do limite (`max_upload_mb`), dataset_id inválido,
    formato não suportado, corrompido ou vazio. Limites default vêm das
    Settings (LOKI_DATASETS_DIR / LOKI_MAX_UPLOAD_MB).
    """
    settings = get_settings()
    base = Path(datasets_dir) if datasets_dir is not None else Path(settings.datasets_dir)
    limit_mb = settings.max_upload_mb if max_upload_mb is None else max_upload_mb
    src = Path(source)
    if not src.is_file():
        raise DataError(f"arquivo não encontrado: {src}")
    if not dataset_id or any(s in dataset_id for s in ("/", "\\")) or dataset_id in (".", ".."):
        raise DataError(f"dataset_id inválido: {dataset_id!r}")
    if version < 1:
        raise DataError(f"version inválida: {version} (mínimo 1)")
    size_bytes = src.stat().st_size
    limit = limit_mb * 1024 * 1024
    if size_bytes > limit:
        raise DataError(
            f"arquivo excede o limite de {limit_mb} MB: '{src.name}' tem {size_bytes} bytes"
        )
    fmt = detect_format(src)
    df, raw_columns = _read(src, fmt)
    dest_dir = base / dataset_id / f"v{version}"
    dest = dest_dir / f"original.{fmt}"
    if dest.exists():
        raise DataError(f"destino já existe (arquivo imutável): {dest}")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    except OSError as exc:
        raise DataError(f"falha ao copiar '{src.name}' para '{dest}': {exc}") from exc
    rows, cols = df.shape
    return IngestResult(
        dataframe=df,
        filename=src.name,
        format=fmt,
        sha256=_sha256(dest),
        size_bytes=size_bytes,
        rows=int(rows),
        cols=int(cols),
        path=str(dest),
        raw_columns=raw_columns,
    )
