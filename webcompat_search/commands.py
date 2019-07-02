import asyncio
import json
import re

import click

from dateutil.parser import parse as dateutilparse

from elasticsearch import Elasticsearch
from github import Github
from tld import get_tld

from webcompat_search import settings
from webcompat_search.prototype_dashboards.data import dump as prototype_dashboards_dump
from webcompat_search.prototype_dashboards.bugzilla import get_bugzilla_webcompat_stats


FQDN_REGEX = re.compile(r"\b(?:[a-z0-9]+(?:-[a-z0-9]+)*\.)+[a-z]{2,}\b")


def get_last_updated_timestamp():
    """Get timestamp of the last updated object."""

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)

    last_updated_q = {
        "sort": [{"updated_at": {"order": "desc"}}],
        "query": {"match_all": {}},
    }
    res = es.search(index=settings.ES_WEBCOMPAT_INDEX, body=last_updated_q)

    last_updated_timestamp = None
    if res["hits"]["hits"]:
        last_updated_timestamp = res["hits"]["hits"][0]["_source"]["updated_at"]

    return last_updated_timestamp


def get_valid_domains(domains):
    """Return list of domains with valid TLDs"""
    valid_domains = []
    for domain in domains:
        res = get_tld(domain, fail_silently=True, fix_protocol=True)
        if res:
            if not (
                domain.endswith("webcompat.com")
                or domain.endswith("githubusercontent.com")
            ):
                valid_domains.append(domain)
    return valid_domains


def get_parsed_url(body):
    """Search for regex to match **URL** in body"""

    o = re.search("\*\*URL\*\*\:\ (.*)", body)  # noqa
    parsed_url = {"scheme": "", "netloc": "", "path": "", "fragment": ""}

    if o:
        url = o.groups()[0]
        try:
            tld = get_tld(url, fix_protocol=True, fail_silently=True, as_object=True)
            parsed_url = {
                "scheme": tld.parsed_url.scheme,
                "netloc": tld.parsed_url.netloc,
                "path": tld.parsed_url.path,
                "fragment": tld.parsed_url.fragment,
            }
        except Exception:
            click.echo("Something went wrong when parsing URL: {}".format(url))
    return parsed_url

def get_extracted_fields(body):
    """Extract the @key: value fields"""

    pattern = "<!-- @(.*): (.*) -->"
    o = re.findall(pattern, body)
    partial_doc = {}
    if o:
        for key, value in o:
            partial_doc['extracted_{}'.format(key)] = value
    return partial_doc

@click.command()
def last_updated():
    click.echo(get_last_updated_timestamp())


@click.command()
@click.option("--state", default="all", help="State of GH issues to fetch")
@click.option("--since", default=None, help="Fetch issues since timestamp (ISO8601)")
def fetch_issues(state, since):
    """Fetch webcompat issues from Github."""

    GITHUB_OWNER = settings.GITHUB_OWNER
    GITHUB_REPO = settings.GITHUB_REPO

    g = Github(settings.GITHUB_API_TOKEN)
    org = g.get_organization(GITHUB_OWNER)
    repo = org.get_repo(GITHUB_REPO)
    kwargs = {"state": state}

    # Get last updated timestamp
    last_updated_timestamp = get_last_updated_timestamp()
    if since or last_updated_timestamp:
        kwargs["since"] = dateutilparse(since or last_updated_timestamp)

    issues = repo.get_issues(**kwargs)

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    es.indices.create(index=settings.ES_WEBCOMPAT_INDEX, ignore=400)

    for i in issues:

        try:
            click.echo("Fetching issue: {}".format(i.id))

            # Prepare ES document object
            body = i.raw_data

            # Query issue title and body to extract domains
            domains = set()
            domains.update(re.findall(FQDN_REGEX, i.title))
            domains.update(re.findall(FQDN_REGEX, i.body))

            body.update({"domains": list(domains)})
            body.update({"valid_domains": get_valid_domains(list(domains))})
            body.update({"parsed_url": get_parsed_url(i.body)})
            body.update(get_extracted_fields(i.body))
            es.index(
                index=settings.ES_WEBCOMPAT_INDEX,
                doc_type="webcompat_issue",
                id=i.number,
                body=body,
            )
        except Exception as e:
            click.echo(str(e), err=True)
            continue


@click.command()
@click.option("--start", default=None, help="Paginated list start range")
@click.option("--end", default=None, help="Paginated list end range")
def fetch_issues_by_range(start, end):
    """Fetch webcompat issues from Github by range in ascending updated order."""

    GITHUB_OWNER = settings.GITHUB_OWNER
    GITHUB_REPO = settings.GITHUB_REPO

    g = Github(settings.GITHUB_API_TOKEN)
    org = g.get_organization(GITHUB_OWNER)
    repo = org.get_repo(GITHUB_REPO)
    kwargs = {"state": "all", "sort": "updated", "direction": "asc"}

    issues = repo.get_issues(**kwargs)

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    es.indices.create(index=settings.ES_WEBCOMPAT_INDEX, ignore=400)

    for elem in range(int(start), int(end)):
        i = issues[elem]
        click.echo("Fetching issue: {}".format(i.id))

        # Prepare ES document object
        body = i.raw_data

        # Query issue title and body to extract domains
        domains = set()
        domains.update(re.findall(FQDN_REGEX, i.title))
        domains.update(re.findall(FQDN_REGEX, i.body))

        body.update({"domains": list(domains)})
        body.update({"valid_domains": get_valid_domains(list(domains))})
        body.update({"parsed_url": get_parsed_url(i.body)})

        es.index(
            index=settings.ES_WEBCOMPAT_INDEX,
            doc_type="webcompat_issue",
            id=i.number,
            body=body,
        )


@click.command()
def reindex_prototype_dashboard_data():
    """Re-index data generated for prototype dashboards"""

    click.echo("Re-index data generated for prototype dashboards")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(prototype_dashboards_dump())
    click.echo("Done!")


@click.command()
def fetch_bugzilla_bugcount():
    click.echo("Fetching bugzilla webcompat bug count")

    with open("webcompat_search/fixtures/top_sites.json", "r") as f:
        top_sites = json.load(f)["top_sites"]

    es = Elasticsearch([settings.ES_URL], **settings.ES_KWARGS)
    es.indices.create(index=settings.BUGZILLA_TOP_SITES_COUNT_INDEX, ignore=400)

    for site in top_sites:
        click.echo("Site: {}".format(site))
        stats = get_bugzilla_webcompat_stats(site)
        es.index(
            index=settings.BUGZILLA_TOP_SITES_COUNT_INDEX,
            doc_type="webcompat_top_bugcount",
            id=stats["site"],
            body=stats,
        )
