from decouple import config


ENV = config('ENV', default='production')
DEBUG = config('DEBUG', default=(ENV == 'development'))
SECRET_KEY = config('SECRET_KEY')
