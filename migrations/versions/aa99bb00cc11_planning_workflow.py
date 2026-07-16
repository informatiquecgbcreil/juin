"""Planning v2 : salles internes/externes + workflow demande/approbation

Revision ID: aa99bb00cc11
Revises: ff667788aa99
Create Date: 2026-07-16

- ``salle``            : est_externe, adresse, contact ;
- ``reservation_salle`` et ``pret_materiel`` : motif, workflow (statut +
  décision + refus) et rappel programmable.

Les réservations / prêts déjà existants sont considérés APPROUVÉS
(server_default 'approuvee') : le workflow ne s'applique qu'aux nouveaux.

Migration DÉFENSIVE et purement ADDITIVE : aucune colonne existante n'est
supprimée ni modifiée.
"""
from alembic import op
import sqlalchemy as sa


revision = "aa99bb00cc11"
down_revision = "ff667788aa99"
branch_labels = None
depends_on = None


def _colonnes(insp, table: str) -> set:
    return {c["name"] for c in insp.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == "sqlite"

    if insp.has_table("salle"):
        cols = _colonnes(insp, "salle")
        if "est_externe" not in cols:
            op.add_column("salle", sa.Column("est_externe", sa.Boolean(), nullable=False, server_default=sa.false()))
            op.create_index("ix_salle_est_externe", "salle", ["est_externe"])
        if "adresse" not in cols:
            op.add_column("salle", sa.Column("adresse", sa.String(length=255), nullable=True))
        if "contact" not in cols:
            op.add_column("salle", sa.Column("contact", sa.String(length=200), nullable=True))

    for table in ("reservation_salle", "pret_materiel"):
        if not insp.has_table(table):
            continue
        cols = _colonnes(insp, table)
        if "motif" not in cols:
            op.add_column(table, sa.Column("motif", sa.String(length=300), nullable=True))
        if "statut" not in cols:
            op.add_column(table, sa.Column("statut", sa.String(length=20), nullable=False, server_default="approuvee"))
            op.create_index(f"ix_{table}_statut", table, ["statut"])
        if "approuve_par_user_id" not in cols:
            # Colonne ajoutée en Integer simple : SQLite ne sait pas ALTER une
            # contrainte de clé étrangère hors « batch mode ». La FK (avec SET
            # NULL) n'est posée que sur PostgreSQL ; l'ORM gère la relation.
            op.add_column(table, sa.Column("approuve_par_user_id", sa.Integer(), nullable=True))
            if not is_sqlite:
                op.create_foreign_key(
                    f"fk_{table}_approuve_par_user_id", table, "user",
                    ["approuve_par_user_id"], ["id"], ondelete="SET NULL",
                )
        if "date_decision" not in cols:
            op.add_column(table, sa.Column("date_decision", sa.DateTime(), nullable=True))
        if "motif_refus" not in cols:
            op.add_column(table, sa.Column("motif_refus", sa.String(length=300), nullable=True))
        if "rappel_jours_avant" not in cols:
            op.add_column(table, sa.Column("rappel_jours_avant", sa.Integer(), nullable=True))
        if "rappel_envoye_at" not in cols:
            op.add_column(table, sa.Column("rappel_envoye_at", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in ("reservation_salle", "pret_materiel"):
        if not insp.has_table(table):
            continue
        cols = _colonnes(insp, table)
        for col in ("rappel_envoye_at", "rappel_jours_avant", "motif_refus",
                    "date_decision", "approuve_par_user_id", "statut", "motif"):
            if col in cols:
                op.drop_column(table, col)

    if insp.has_table("salle"):
        cols = _colonnes(insp, "salle")
        for col in ("contact", "adresse", "est_externe"):
            if col in cols:
                op.drop_column("salle", col)
