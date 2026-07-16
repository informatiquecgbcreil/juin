"""Planning interne : salles, réservations, prêts de matériel

Revision ID: ff667788aa99
Revises: ee55ff667788
Create Date: 2026-07-16

- ``salle``              : salles / espaces réservables ;
- ``reservation_salle``  : réservations (jour + heures), conflit géré côté service ;
- ``pret_materiel``      : prêts (sortie/retour) des items d'inventaire.

Migration DÉFENSIVE et purement ADDITIVE : aucune table ni colonne existante
n'est modifiée.
"""
from alembic import op
import sqlalchemy as sa


revision = "ff667788aa99"
down_revision = "ee55ff667788"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("salle"):
        op.create_table(
            "salle",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nom", sa.String(length=160), nullable=False),
            sa.Column("secteur", sa.String(length=80), nullable=True),
            sa.Column("capacite", sa.Integer(), nullable=True),
            sa.Column("localisation", sa.String(length=200), nullable=True),
            sa.Column("couleur", sa.String(length=20), nullable=True),
            sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_salle_secteur", "salle", ["secteur"])
        op.create_index("ix_salle_actif", "salle", ["actif"])

    if not insp.has_table("reservation_salle"):
        op.create_table(
            "reservation_salle",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("salle_id", sa.Integer(), sa.ForeignKey("salle.id", ondelete="CASCADE"), nullable=False),
            sa.Column("titre", sa.String(length=200), nullable=False),
            sa.Column("date_reservation", sa.Date(), nullable=False),
            sa.Column("heure_debut", sa.String(length=5), nullable=False),
            sa.Column("heure_fin", sa.String(length=5), nullable=False),
            sa.Column("secteur", sa.String(length=80), nullable=True),
            sa.Column("session_id", sa.Integer(), sa.ForeignKey("session_activite.id", ondelete="SET NULL"), nullable=True),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_reservation_salle_salle_id", "reservation_salle", ["salle_id"])
        op.create_index("ix_reservation_salle_date_reservation", "reservation_salle", ["date_reservation"])
        op.create_index("ix_reservation_salle_secteur", "reservation_salle", ["secteur"])
        op.create_index("ix_reservation_salle_session_id", "reservation_salle", ["session_id"])
        op.create_index("ix_reservation_salle_jour", "reservation_salle", ["salle_id", "date_reservation"])

    if not insp.has_table("pret_materiel"):
        op.create_table(
            "pret_materiel",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("item_id", sa.Integer(), sa.ForeignKey("inventaire_item.id", ondelete="CASCADE"), nullable=False),
            sa.Column("emprunteur", sa.String(length=200), nullable=False),
            sa.Column("quantite", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("date_pret", sa.Date(), nullable=False),
            sa.Column("date_retour_prevue", sa.Date(), nullable=True),
            sa.Column("date_retour_reel", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(length=500), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_pret_materiel_item_id", "pret_materiel", ["item_id"])
        op.create_index("ix_pret_materiel_date_pret", "pret_materiel", ["date_pret"])
        op.create_index("ix_pret_materiel_date_retour_prevue", "pret_materiel", ["date_retour_prevue"])
        op.create_index("ix_pret_materiel_date_retour_reel", "pret_materiel", ["date_retour_reel"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in ("pret_materiel", "reservation_salle", "salle"):
        if insp.has_table(table):
            op.drop_table(table)
