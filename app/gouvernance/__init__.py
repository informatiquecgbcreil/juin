from flask import Blueprint

bp = Blueprint("gouvernance", __name__, url_prefix="/gouvernance")

from . import routes  # noqa: E402,F401
