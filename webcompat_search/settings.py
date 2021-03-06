import json

from decouple import config


ENV = config("ENV", default="production")
DEBUG = config("DEBUG", default=(ENV == "development"))
SECRET_KEY = config("SECRET_KEY")
GITHUB_OWNER = config("GITHUB_OWNER", default="webcompat")
GITHUB_REPO = config("GITHUB_REPO", default="web-bugs")
GITHUB_API_TOKEN = config("GITHUB_API_TOKEN")
ES_URL = config("ES_URL", default="http://es:9200")
ES_KWARGS = config("ES_KWARGS", default="{}", cast=json.loads)
ES_WEBCOMPAT_INDEX = config("ES_WEBCOMPAT_INDEX", default="webcompat_bugs")
ES_QUERY_SIZE = config("ES_QUERY_SIZE", default=1000, cast=int)
ES_SCROLL_LIMIT = config("ES_SCROLL_LIMIT", default="1m")
BUGZILLA_DUPED_INDEX = config("BUGZILLA_DUPED_INDEX", default="bugzilla_duped")
BUGZILLA_PARTNER_REGRESSION_BUGS = config(
    "BUGZILLA_PARTNER_REGRESSION_BUGS", default="bugzilla_regression_partners"
)
BUGZILLA_TOP_SITES_COUNT_INDEX = config(
    "BUGZILLA_COUNT_INDEX", default="bugzilla_top_sites_count"
)
