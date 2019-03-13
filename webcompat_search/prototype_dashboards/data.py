import asyncio
import attr
import datetime as dt
import dateutil
import json
import os
import pandas as pd
import pytz
import re
import requests

from aioelasticsearch.helpers import Scan
from aioelasticsearch import Elasticsearch
from collections import Counter
from dateutil.rrule import rrule, DAILY
from typing import List
from urllib.parse import urlencode

from webcompat_search import settings
from webcompat_search.settings import (
    BUGZILLA_DUPED_INDEX,
    BUGZILLA_PARTNER_REGRESSION_BUGS,
)

ES_HOST = "127.0.0.1:9200"


world_ranks_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "fixtures/world_ranks.json"
)

with open(world_ranks_path, "r") as f:
    world_ranks = json.load(f)


async def load_issues():
    async with Elasticsearch(hosts=[settings.ES_URL], **settings.ES_KWARGS) as es:
        async with Scan(
            es,
            query={"query": {"match_all": {}}},
            index="webcompat_ecf7ba1c",
            scroll="120m",
        ) as scan:
            rows = []
            async for doc in scan:
                try:
                    domain = doc["_source"]["valid_domains"][0]
                except IndexError:
                    domain = None

                print("Loading: {}".format(doc["_id"]))
                d = {
                    "number": doc["_source"]["number"],
                    "created_at": doc["_source"]["created_at"],
                    "closed_at": doc["_source"]["closed_at"],
                    "domain": domain,
                    "state": doc["_source"]["state"],
                }
                rows.append(d)

            df = pd.DataFrame(rows)
            df.closed_at = pd.to_datetime(df.closed_at)
            df.created_at = pd.to_datetime(df.created_at)
            hostname_re = r"(.*://)?(www\.)?([^:/]+)[:/]?.*"
            df["hostname"] = df.domain.str.extract(hostname_re)[2]
    return df


async def update_index(result):
    async with Elasticsearch(hosts=[settings.ES_URL], **settings.ES_KWARGS) as es:
        # Wipe indices
        delete_query = {"query": {"match_all": {}}}

        await es.delete_by_query(
            index=BUGZILLA_DUPED_INDEX, body=delete_query, doc_type=BUGZILLA_DUPED_INDEX
        )
        for bug in result["bugzilla"]:
            await es.index(
                index=BUGZILLA_DUPED_INDEX, doc_type=BUGZILLA_DUPED_INDEX, body=bug
            )

        await es.delete_by_query(
            index=BUGZILLA_PARTNER_REGRESSION_BUGS,
            body=delete_query,
            doc_type=BUGZILLA_PARTNER_REGRESSION_BUGS,
        )
        for partner in result["by_partner"]:
            for regression_bug in result["by_partner"][partner]["regression_bugs"]:
                regression_bug["partner"] = partner
                await es.index(
                    index=BUGZILLA_PARTNER_REGRESSION_BUGS,
                    doc_type=BUGZILLA_PARTNER_REGRESSION_BUGS,
                    body=regression_bug,
                )


def fetch_bugzilla_webcompat_bugs():
    bugs = requests.get(
        "https://bugzilla.mozilla.org/rest/bug",
        params={
            "o1": "regexp",
            "v1": ".*webcompat.*",
            "f1": "see_also",
            "limit": 0,
            "include_fields": [
                "id",
                "summary",
                "product",
                "component",
                "votes",
                "creation_time",
                "last_change_time",
                "status",
                "resolution",
                "see_also",
            ],
        },
    ).json()["bugs"]
    return bugs


def fetch_bugzilla_partner_rel_bugs():
    return requests.get(
        "https://bugzilla.mozilla.org/rest/bug",
        {"status_whiteboard_type": "substring", "status_whiteboard": "[platform-rel"},
    ).json()["bugs"]


@attr.s
class PlatformRelSpec:
    _SEARCH_URL = "https://bugzilla.mozilla.org/buglist.cgi"

    include: List[str] = attr.ib(factory=list)
    exclude: List[str] = attr.ib(factory=list)

    def prefixed_include(self):
        yield from ("platform-rel-{}".format(tag) for tag in self.include)

    def prefixed_exclude(self):
        yield from ("platform-rel-{}".format(tag) for tag in self.exclude)

    def sitewait_query_url(self):
        clauses = {"f1": "status_whiteboard", "o1": "substring", "v1": "[sitewait]"}
        clauses.update(self._bugzilla_clauses(2))
        return self._SEARCH_URL + "?" + urlencode(clauses)

    def regression_query_url(self):
        clauses = {"keywords": "regression", "keywords_type": "allwords"}
        clauses.update(self._bugzilla_clauses(1))
        return self._SEARCH_URL + "?" + urlencode(clauses)

    def open_query_url(self):
        return self._SEARCH_URL + "?" + urlencode(self._bugzilla_clauses(1))

    def _bugzilla_clauses(self, field_start):
        field = field_start
        clauses = {
            "resolution": "---",
            "query_format": "advanced",
            "f%d" % field: "OP",
            "j%d" % field: "OR",
        }
        field += 1
        for tag in self.prefixed_include():
            clauses["f%d" % field] = "status_whiteboard"
            clauses["o%d" % field] = "substring"
            clauses["v%d" % field] = "[%s]" % tag
            field += 1
        clauses["f%d" % field] = "CP"
        field += 1
        if len(self.exclude) == 0:
            return clauses
        clauses["f%d" % field] = "OP"
        clauses["n%d" % field] = 1
        field += 1
        for tag in self.prefixed_exclude():
            clauses["f%d" % field] = "status_whiteboard"
            clauses["o%d" % field] = "substring"
            clauses["v%d" % field] = "[%s]" % tag
            field += 1
        return clauses


SITE_TO_TAGS = {
    "youtube.com": PlatformRelSpec(["youtube"]),
    "baidu.com": PlatformRelSpec(["baidu"]),
    "wikipedia.org": PlatformRelSpec(["wikipedia", "wikimedia"]),
    "yahoo.com": PlatformRelSpec(["yahoo!"]),
    "reddit.com": PlatformRelSpec(["reddit"]),
    "amazon.com": PlatformRelSpec(
        ["amazon", "amazonmusic", "amazonshopping", "amazonvideo"]
    ),
    "twitter.com": PlatformRelSpec(["twitter"]),
    "live.com": PlatformRelSpec(["microsoft"]),
    "yandex.ru": PlatformRelSpec(["yandex"]),
    "google.com": PlatformRelSpec(
        include=[
            "google",
            "googlecalendar",
            "googledocs",
            "googlehangouts",
            "googlemaps",
            "googlesheets",
            "googleslides",
            "googlesuite",
        ],
        exclude=["youtube"],
    ),
    "whatsapp.com": PlatformRelSpec(["whatsappweb"]),
    "facebook.com": PlatformRelSpec(
        include=["facebook"], exclude=["whatsappweb", "instagram"]
    ),
}


def sort_partner_rel_bugs(bugs):
    by_partner = {}
    for bug in bugs:
        tags = re.findall(r"\[([^\]]+)\]", bug["whiteboard"].lower())
        for partner, spec in SITE_TO_TAGS.items():
            if any(tag in spec.prefixed_exclude() for tag in tags):
                continue
            if any(tag in spec.prefixed_include() for tag in tags):
                by_partner.setdefault(partner, []).append(bug)
    return by_partner


def annotate_rankings(d):
    to_rename = []
    for key in d:
        for site in world_ranks:
            if key == site or key.endswith(f".{site}"):
                to_rename.append((key, site))
                break
    for key, site in to_rename:
        d[f"{key} {world_ranks[site]}"] = d.pop(key)
    return d


async def dump():
    df = await load_issues()

    result = {"last_updated": dt.datetime.now().isoformat()}

    # Top open domains
    result["open"] = (
        df.loc[
            (df.state == "open") & ~df.hostname.isnull() & (df.hostname != "None"), :
        ]
        .groupby("hostname")["number"]
        .count()
        .sort_values(ascending=False)[:10]
        .to_dict()
    )
    result["open"] = annotate_rankings(result["open"])

    # Top domains, last 30 days

    result["last30"] = (
        df.loc[
            (df.created_at >= dt.datetime.now(pytz.utc) - dt.timedelta(days=30))
            & ~df.hostname.isnull()
            & (df.hostname != "None"),
            :,
        ]
        .groupby("hostname")["number"]
        .count()
        .sort_values(ascending=False)[:10]
        .to_dict()
    )
    result["last30"] = annotate_rankings(result["last30"])

    bugzilla_see_also = fetch_bugzilla_webcompat_bugs()
    bz = pd.DataFrame(bugzilla_see_also).set_index("id")

    # Make a mapping of bugzilla ID <-see also-> webcompat bugs
    join_table_rows = []
    for key, urls in bz["see_also"].items():
        for url in urls:
            if "webcompat" not in url:
                continue
            m = re.search(r"\d{2,}", url)
            if not m:
                continue
            webcompat_id = int(m[0])
            join_table_rows.append({"bugzilla_id": key, "webcompat_id": webcompat_id})
    join_table = pd.DataFrame(
        join_table_rows, columns=["bugzilla_id", "webcompat_id"]
    ).drop_duplicates()

    wc_dupes = join_table.merge(
        # fetch indices of open bugs
        bz.query(
            "status == 'UNCONFIRMED' or status == 'NEW' "
            "or status == 'ASSIGNED' or status == 'REOPENED'"
        )[[]],
        how="inner",
        left_on="bugzilla_id",
        right_index=True,
    ).merge(
        df[["number", "hostname"]],
        how="left",
        left_on="webcompat_id",
        right_on="number",
    )

    n_dupes = wc_dupes.groupby("bugzilla_id")["webcompat_id"].count()
    most_duped = (
        wc_dupes.groupby("bugzilla_id")["webcompat_id"]
        .count()
        .sort_values(ascending=False)[:10]
    )

    def most_common(col):
        c = Counter(col)
        result = []
        for key, n in c.most_common(3):
            if not isinstance(key, str):
                continue
            for site in world_ranks:
                if key == site or key.endswith(f".{site}"):
                    key = f"{key} {world_ranks[site]}"
                    break
            result.append(f"{key} ({n})")
        return ", ".join(result)

    domains_per_bz_issue = wc_dupes.groupby("bugzilla_id")["hostname"].agg(most_common)

    annotated = bz.copy()
    annotated["most_reported"] = domains_per_bz_issue
    annotated["wc_dupes"] = n_dupes

    result["bugzilla"] = (
        annotated.loc[
            most_duped.index, ["wc_dupes", "component", "summary", "most_reported"]
        ]
        .reset_index()
        .to_dict(orient="records")
    )

    # Assemble per-partner results
    partner_rel_bugs = fetch_bugzilla_partner_rel_bugs()
    by_partner = sort_partner_rel_bugs(partner_rel_bugs)

    dates_x = [
        x.date()
        for x in rrule(DAILY, dtstart=dt.date(2016, 1, 1), until=dt.date.today())
    ]
    result["dates_x"] = [d.isoformat() for d in dates_x]

    retain_keys = ["id", "summary", "resolution"]
    subset = {}
    for partner, bugs in by_partner.items():
        regression_bugs = []
        open_bugs = [0] * len(dates_x)
        n_open = 0
        n_sitewait = 0
        n_regression = 0
        bugs = sorted(
            bugs,
            key=lambda bug: dateutil.parser.parse(bug["creation_time"]),
            reverse=True,
        )
        for bug in bugs:
            if bug["resolution"] == "":
                n_open += 1
                if "regression" in bug["keywords"]:
                    regression_bugs.append({k: bug[k] for k in retain_keys})
                    n_regression += 1
                n_sitewait += 1 if "sitewait" in bug["whiteboard"].lower() else 0
            created = dateutil.parser.parse(bug["creation_time"]).date()
            if bug["cf_last_resolved"]:
                last_resolved = dateutil.parser.parse(bug["cf_last_resolved"]).date()
            else:
                last_resolved = dt.date.max
            for j, d in enumerate(dates_x):
                if created <= d <= last_resolved:
                    open_bugs[j] += 1
        d = {
            "summary": {
                "n_open": n_open,
                "open_url": SITE_TO_TAGS[partner].open_query_url(),
                "n_sitewait": n_sitewait,
                "sitewait_url": SITE_TO_TAGS[partner].sitewait_query_url(),
                "n_regression": n_regression,
                "regression_url": SITE_TO_TAGS[partner].regression_query_url(),
                "open_bugs_y": open_bugs,
            },
            "regression_bugs": regression_bugs,
        }
        subset[partner] = d
    result["by_partner"] = subset

    return await update_index(result)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    output = loop.run_until_complete(dump())
