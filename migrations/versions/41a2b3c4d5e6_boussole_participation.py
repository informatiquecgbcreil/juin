"""Boussole participation et pouvoir d'agir.

Revision ID: 41a2b3c4d5e6
Revises: f4a5b6c7d8e9, e6f7a8b9c0d1
Create Date: 2026-07-01
"""
import sqlalchemy as sa
from alembic import op

revision = "41a2b3c4d5e6"
down_revision = ("f4a5b6c7d8e9", "e6f7a8b9c0d1")
branch_labels = None
depends_on = None

TABLE = "boussole_participation"


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("participant_id", sa.Integer(), sa.ForeignKey("participant.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("session_activite.id", ondelete="SET NULL"), nullable=True),
        sa.Column("secteur", sa.String(length=80), nullable=False),
        sa.Column("action_label", sa.String(length=180), nullable=True),
        sa.Column("date_observation", sa.Date(), nullable=False),
        sa.Column("niveau", sa.Integer(), nullable=False),
        sa.Column("niveau_precedent", sa.Integer(), nullable=True),
        sa.Column("evolution", sa.String(length=20), nullable=False, server_default="stable"),
        sa.Column("jalon", sa.String(length=40), nullable=False, server_default="ajustement"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="pro"),
        sa.Column("statut_validation", sa.String(length=30), nullable=False, server_default="observee"),
        sa.Column("visibilite", sa.String(length=30), nullable=False, server_default="interne"),
        sa.Column("indicators_json", sa.Text(), nullable=True),
        sa.Column("presence_count_snapshot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("remarque", sa.Text(), nullable=True),
        sa.Column("temoignage", sa.Text(), nullable=True),
        sa.Column("bilan", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for col in ("participant_id", "session_id", "secteur", "action_label", "date_observation", "niveau", "evolution", "jalon", "source", "statut_validation", "visibilite", "created_at"):
        op.create_index(f"ix_{TABLE}_{col}", TABLE, [col])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(TABLE):
        op.drop_table(TABLE)
