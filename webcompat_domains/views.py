from flask import Blueprint
from flask.json import jsonify

from elasticsearch import Elasticsearch

from webcompat_domains import settings


blueprint = Blueprint('domains', __name__)


@blueprint.route('/healthz', methods=['GET'])
def get_health():
    """Health check endpoint."""

    return jsonify({'status': 'OK'})


@blueprint.route('/domain/<domain>')
def get_domain(domain):
    """Query for issues based on domain"""

    es = Elasticsearch([settings.ES_URL])
    query = {
        "query": {
            "term": {
                "domains": domain
            }
        }
    }
    res = es.search(index=settings.ES_WEBCOMPAT_INDEX, body=query)
    return jsonify(res['hits']['hits'])
