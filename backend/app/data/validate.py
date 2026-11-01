"""Validação de dataframes lidos pela ingestão — erros claros via DataError.

Regras, nesta ordem:
1. sem colunas: o dataframe não tem nenhuma coluna;
2. colunas duplicadas: nomes repetidos no cabeçalho (o pandas renomeia as
   duplicatas do CSV para `a.1`, por isso o cabeçalho cru pode ser informado
   via `raw_columns` — sem ele, a checagem usa os nomes já lidos);
3. arquivo vazio: 0 linhas após a leitura;
4. apenas 1 linha: mínimo de 2 linhas para estatística e splits.
"""

from collections.abc import Sequence

import pandas as pd

from app.data.errors import DataError


def validate_columns(columns: Sequence[str]) -> None:
    """Levanta DataError se houver nomes de coluna repetidos na sequência."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for column in columns:
        name = str(column)
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise DataError(f"colunas duplicadas: {', '.join(duplicates)}")


def validate_dataframe(
    df: pd.DataFrame, *, raw_columns: Sequence[str] | None = None
) -> None:
    """Valida o dataframe; levanta DataError com mensagem clara na primeira falha.

    `raw_columns` são os nomes do cabeçalho cru (CSV), quando o leitor pode
    ter renomeado duplicatas — a checagem de duplicatas usa-os também.
    """
    if len(df.columns) == 0:
        raise DataError("sem colunas: o arquivo não possui nenhuma coluna")
    validate_columns(list(df.columns))
    if raw_columns is not None:
        validate_columns(list(raw_columns))
    if len(df) == 0:
        raise DataError("arquivo vazio: 0 linhas após a leitura")
    if len(df) == 1:
        raise DataError("apenas 1 linha: o dataset precisa de pelo menos 2 linhas")
