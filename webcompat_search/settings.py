import json

from decouple import config


ENV = config('ENV', default='production')
DEBUG = config('DEBUG', default=(ENV == 'development'))
SECRET_KEY = config('SECRET_KEY')
GITHUB_OWNER = config('GITHUB_OWNER', default='webcompat')
GITHUB_REPO = config('GITHUB_REPO', default='web-bugs')
GITHUB_API_TOKEN = config('GITHUB_API_TOKEN')
ES_URL = config('ES_URL', default='http://es:9200')
ES_KWARGS = config('ES_KWARGS', default='{}', cast=json.loads)
ES_WEBCOMPAT_INDEX = config('ES_WEBCOMPAT_INDEX', default='webcompat_bugs')
