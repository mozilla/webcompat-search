from urllib.parse import urlencode
from requests_html import HTMLSession


def get_bugzilla_webcompat_stats(website):
    """Fetch bugzilla bug count for top sites."""

    bugzilla_url = "https://bugzilla.mozilla.org/buglist.cgi"
    query_list = [
        ("bug_file_loc_type", "allwordssubstr"),
        ("list_id", "14485116"),
        ("resolution", "---"),
        ("bug_file_loc", website),
        ("query_format", "advanced"),
        ("bug_status", "UNCONFIRMED"),
        ("bug_status", "NEW"),
        ("bug_status", "ASSIGNED"),
        ("bug_status", "REOPENED"),
        ("product", "Core"),
        ("product", "Firefox"),
        ("product", "Firefox for Android"),
        ("product", "Web Compatibility"),
    ]
    url_params = urlencode(query_list)
    query = "{}?{}".format(bugzilla_url, url_params)

    session = HTMLSession()
    r = session.get(query)
    try:
        count_el = r.html.find("span.bz_result_count", first=True)
        count = int(count_el.text.rstrip("bugs found."))
    except:
        count = 0

    parsed_url = {
        "scheme": "",
        "netloc": website,
        "path": "",
        "fragment": ""
    }
    return {"site": website, "url": query, "bugs_count": count, "parsed_url": parsed_url}
