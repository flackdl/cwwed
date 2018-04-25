"""
Django settings for cwwed project.

Generated by 'django-admin startproject' using Django 2.0.1.

For more information on this file, see
https://docs.djangoproject.com/en/2.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.0/ref/settings/
"""

import os
import sys
import dj_database_url

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'ssshhh...')

# SECURITY WARNING: don't run with debug turned on in production!
# TODO
DEBUG = True

# TODO
# https://docs.djangoproject.com/en/2.0/topics/security/#host-headers-virtual-hosting
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'named_storms.apps.NamedStormsConfig',  # specify AppConfig to include custom signals
    'audit',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',  # for drf
    'corsheaders',  # for drf
    'revproxy',  # django-revproxy
    'storages',  # django-storages
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'crispy_forms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cwwed.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

FILE_UPLOAD_HANDLERS = [
    # stream directly to temporary disk space
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',

    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
)

WSGI_APPLICATION = 'cwwed.wsgi.application'


# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    # https://github.com/kennethreitz/dj-database-url
    'default': dj_database_url.config(default='postgis://postgres@localhost:5432/postgres', conn_max_age=300),
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'


# Logging
# https://docs.djangoproject.com/en/2.0/topics/logging/
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    # log everything to the console
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

SITE_ID = 1

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
    ),
}

# django-cors-headers
# https://github.com/ottoyiu/django-cors-headers/
CORS_URLS_REGEX = r'^/api/.*$'
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_METHODS = (
    'GET',
    'OPTIONS',
)

#
# CWWED
#

CWWED_ARCHIVE_EXTENSION = 'tar'
CWWED_DATA_DIR = '/media/bucket/cwwed'
CWWED_COVERED_DATA_DIR_NAME = 'Covered Data'
CWWED_COVERED_DATA_INCOMPLETE_DIR_NAME = '.incomplete'
CWWED_COVERED_DATA_ARCHIVE_TYPE = 'gztar'
CWWED_NSEM_DIR_NAME = 'NSEM'
CWWED_NSEM_ARCHIVE_INPUT_NAME = 'covered-data.{}'.format(CWWED_ARCHIVE_EXTENSION)
CWWED_NSEM_ARCHIVE_WRITE_MODE = 'w'
CWWED_NSEM_ARCHIVE_CONTENT_TYPE = 'application/tar'
CWWED_NSEM_USER = 'nsem'
CWWED_NSEM_PERMISSION_DOWNLOAD_DATA = 'download_nsem_data'
CWWED_NSEM_PASSWORD = os.environ.get('CWWED_NSEM_PASSWORD', 'cookie123')

THREDDS_URL = 'http://{}:9000/thredds/'.format(os.environ.get('THREDDS_HOST', 'localhost'))

SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
