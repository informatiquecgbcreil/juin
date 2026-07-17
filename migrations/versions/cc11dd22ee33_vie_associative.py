"""Vie associative : instances de gouvernance, mandats, réunions, émargement

Revision ID: cc11dd22ee33
Revises: bb00cc11dd22
Create Date: 2026-07-17

Nouvelles tables (aucune table existante n'est modifiée) :
- ``instance_gouvernance`` : AG, conseil d'administration, bureau, commissions ;
- ``mandat``               : mandats (fonction + échéance) dans une instance ;
- ``reunion_instance``     : réunions / AG (ordre du jour, quorum, relevé) ;
- ``presence_reunion``     : émargement (présent / représenté / excusé).

Migration DÉFENSIVE : chaque table n'est créée que si absente.
"""
from alembic import op
import sqlalchemy as sa


revision = "cc11dd22ee33"
down_revision = "bb00cc11dd22"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("instance_gouvernance"):
        op.create_table(
            "instance_gouvernance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nom", sa.String(length=160), nullable=False),
            sa.Column("type_instance", sa.String(length=20), nullable=False, server_default="ca"),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_instance_gouvernance_type_instance", "instance_gouvernance", ["type_instance"])
        op.create_index("ix_instance_gouvernance_actif", "instance_gouvernance", ["actif"])

    if not insp.has_table("mandat"):
        op.create_table(
            "mandat",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("instance_id", sa.Integer(), sa.ForeignKey("instance_gouvernance.id", ondelete="CASCADE"), nullable=False),
            sa.Column("nom", sa.String(length=200), nullable=False),
            sa.Column("fonction", sa.String(length=30), nullable=False, server_default="membre"),
            sa.Column("email", sa.String(length=200), nullable=True),
            sa.Column("telephone", sa.String(length=40), nullable=True),
            sa.Column("participant_id", sa.Integer(), sa.ForeignKey("participant.id", ondelete="SET NULL"), nullable=True),
            sa.Column("date_debut", sa.Date(), nullable=True),
            sa.Column("date_fin", sa.Date(), nullable=True),
            sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("alerte_echeance_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_mandat_instance_id", "mandat", ["instance_id"])
        op.create_index("ix_mandat_participant_id", "mandat", ["participant_id"])
        op.create_index("ix_mandat_date_fin", "mandat", ["date_fin"])
        op.create_index("ix_mandat_actif", "mandat", ["actif"])

    if not insp.has_table("reunion_instance"):
        op.create_table(
            "reunion_instance",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("instance_id", sa.Integer(), sa.ForeignKey("instance_gouvernance.id", ondelete="CASCADE"), nullable=False),
            sa.Column("type_reunion", sa.String(length=20), nullable=False, server_default="reunion"),
            sa.Column("titre", sa.String(length=200), nullable=False),
            sa.Column("date_reunion", sa.Date(), nullable=False),
            sa.Column("heure", sa.String(length=5), nullable=True),
            sa.Column("lieu", sa.String(length=200), nullable=True),
            sa.Column("ordre_du_jour", sa.Text(), nullable=True),
            sa.Column("statut", sa.String(length=20), nullable=False, server_default="planifiee"),
            sa.Column("base_electeurs", sa.Integer(), nullable=True),
            sa.Column("quorum_requis", sa.Integer(), nullable=True),
            sa.Column("releve_decisions", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_reunion_instance_instance_id", "reunion_instance", ["instance_id"])
        op.create_index("ix_reunion_instance_date_reunion", "reunion_instance", ["date_reunion"])
        op.create_index("ix_reunion_instance_statut", "reunion_instance", ["statut"])

    if not insp.has_table("presence_reunion"):
        op.create_table(
            "presence_reunion",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reunion_id", sa.Integer(), sa.ForeignKey("reunion_instance.id", ondelete="CASCADE"), nullable=False),
            sa.Column("nom", sa.String(length=200), nullable=False),
            sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("pouvoir", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("excuse", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("represente_par", sa.String(length=200), nullable=True),
            sa.Column("mandat_id", sa.Integer(), sa.ForeignKey("mandat.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_presence_reunion_reunion_id", "presence_reunion", ["reunion_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in ("presence_reunion", "reunion_instance", "mandat", "instance_gouvernance"):
        if insp.has_table(table):
            op.drop_table(table)
