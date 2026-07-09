from flask import Blueprint

items_bp = Blueprint('items', __name__)

from app.items import routes
