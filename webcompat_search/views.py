from flask import Blueprint, url_for
from flask.json import jsonify

from elasticsearch import Elasticsearch

from webcompat_search import settings


blueprint = Blueprint('domains', __name__)


@blueprint.route('/healthz', methods=['GET'])
def get_health():
    """Health check endpoint."""

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    es_health = es.cluster.health()
    status_code = 200 if es_health['status'] == 'green' else 500
    healthz = {
        'ES': es_health
    }

    return jsonify(healthz), status_code


@blueprint.route('/', methods=['GET'])
def get_schema():
    """API schema"""

    schema = {
        'search_by_domain': url_for('.get_domain', domain='_domain_')
    }
    return jsonify(schema)


@blueprint.route('/domain/<domain>')
def get_domain(domain):
    """Query for issues based on domain"""

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    query = {
        "query": {
            "term": {
                "domains": domain
            }
        }
    }
    res = es.search(index=settings.ES_WEBCOMPAT_INDEX, body=query)
    return jsonify(res['hits']['hits'])
