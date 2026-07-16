from flask import Blueprint

bp = Blueprint("planning", __name__, url_prefix="/planning")

from . import routes  # noqa: E402,F401
