"""initial — FASE 1 sem tabelas (os modelos chegam na FASE 2+).

Revision ID: 0001
Revises:
Create Date: 2026-11-01
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nenhuma tabela na FASE 1: só o controle de revisões (alembic_version)."""
    pass


def downgrade() -> None:
    """Nada a reverter: nenhuma tabela foi criada."""
    pass
