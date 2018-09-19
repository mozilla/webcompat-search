from decouple import config


ENV = config('ENV', default='production')
DEBUG = config('DEBUG', default=(ENV == 'development'))
SECRET_KEY = config('SECRET_KEY')
GITHUB_API_TOKEN = config('GITHUB_API_TOKEN')
ES_URL = config('ES_URL', default='http://es:9200')
ES_WEBCOMPAT_INDEX = config('ES_WEBCOMPAT_INDEX', default='webcompat_bugs')