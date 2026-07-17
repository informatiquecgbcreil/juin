"""Planning : location payante de salles et de matériel

Revision ID: bb00cc11dd22
Revises: aa99bb00cc11
Create Date: 2026-07-16

Une réservation de salle ou un prêt de matériel peut être une mise à
disposition FACTURÉE (location), en plus du prêt gratuit existant :
- ``est_location`` distingue les deux (défaut False = gratuit) ;
- tarif (montant + base : heure/jour/forfait), caution, suivi du paiement,
  coordonnées du locataire.

Migration DÉFENSIVE et purement ADDITIVE : colonnes ajoutées seulement si
absentes, toutes nullables ou avec valeur par défaut ; les réservations /
prêts existants restent des opérations gratuites (est_location=False).
"""
from alembic import op
import sqlalchemy as sa


revision = "bb00cc11dd22"
down_revision = "aa99bb00cc11"
branch_labels = None
depends_on = None


def _colonnes(insp, table: str) -> set:
    return {c["name"] for c in insp.get_columns(table)}


#: Colonnes communes aux deux tables (nom -> constructeur de colonne).
def _colonnes_location(inclure_locataire: bool):
    cols = [
        ("est_location", lambda: sa.Column("est_location", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("contact", lambda: sa.Column("contact", sa.String(length=200), nullable=True)),
        ("tarif_montant", lambda: sa.Column("tarif_montant", sa.Float(), nullable=True)),
        ("tarif_unite", lambda: sa.Column("tarif_unite", sa.String(length=10), nullable=True)),
        ("caution_montant", lambda: sa.Column("caution_montant", sa.Float(), nullable=True)),
        ("caution_rendue", lambda: sa.Column("caution_rendue", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("paiement_statut", lambda: sa.Column("paiement_statut", sa.String(length=20), nullable=False, server_default="a_regler")),
        ("paiement_mode", lambda: sa.Column("paiement_mode", sa.String(length=20), nullable=True)),
        ("paiement_date", lambda: sa.Column("paiement_date", sa.Date(), nullable=True)),
    ]
    if inclure_locataire:
        cols.insert(1, ("locataire", lambda: sa.Column("locataire", sa.String(length=200), nullable=True)))
    return cols


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, avec_locataire in (("reservation_salle", True), ("pret_materiel", False)):
        if not insp.has_table(table):
            continue
        cols = _colonnes(insp, table)
        for nom, fabrique in _colonnes_location(avec_locataire):
            if nom not in cols:
                op.add_column(table, fabrique())
        if "est_location" in _colonnes(insp, table):
            existing_idx = {i["name"] for i in insp.get_indexes(table)}
            idx = f"ix_{table}_est_location"
            if idx not in existing_idx:
                op.create_index(idx, table, ["est_location"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, avec_locataire in (("reservation_salle", True), ("pret_materiel", False)):
        if not insp.has_table(table):
            continue
        cols = _colonnes(insp, table)
        for nom, _ in reversed(_colonnes_location(avec_locataire)):
            if nom in cols:
                op.drop_column(table, nom)
