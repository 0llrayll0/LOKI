"""Erros claros do pipeline de dados (FASE 2)."""


class DataError(Exception):
    """Falha de ingestão, validação ou preparação com mensagem explicando o problema."""
