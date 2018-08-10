from flask import Blueprint
from flask.json import jsonify


blueprint = Blueprint('domains', __name__)


@blueprint.route('/healthz', methods=['GET'])
def get_health():
    """Health check endpoint."""

    return jsonify({'status': 'OK'})
