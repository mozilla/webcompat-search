import re

import click

from elasticsearch import Elasticsearch
from github import Github

from webcompat_search import settings


FQDN_REGEX = re.compile(r'\b(?:[a-z0-9]+(?:-[a-z0-9]+)*\.)+[a-z]{2,}\b')


@click.command()
@click.option('--state', default='all', help='State of GH issues to fetch')
def fetch_issues(state):
    """Fetch webcompat issues from Github."""

    GITHUB_OWNER = 'webcompat'
    GITHUB_REPO = 'web-bugs'

    g = Github(settings.GITHUB_API_TOKEN)
    org = g.get_organization(GITHUB_OWNER)
    repo = org.get_repo(GITHUB_REPO)
    issues = repo.get_issues(state=state)

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    es.indices.create(index=settings.ES_WEBCOMPAT_INDEX, ignore=400)

    for i in issues:

        # Prepare ES document object
        body = i.raw_data

        # Query issue title and body to extract domains
        domains = set()
        domains.update(re.findall(FQDN_REGEX, i.title))
        domains.update(re.findall(FQDN_REGEX, i.body))

        body.update({'domains': list(domains)})

        es.index(
            index=settings.ES_WEBCOMPAT_INDEX,
            doc_type='webcompat_issue',
            id=i.number,
            body=body
        )
