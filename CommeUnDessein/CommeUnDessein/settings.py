"""
Django settings for Comme Un Dessein project.

Generated by 'django-admin startproject' using Django 1.9.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

from django.conf import global_settings
import sys
import os
import json
from mongoengine import *
connect('CommeUnDessein')

with open('/data/settings.json') as f:
    localSettings = json.loads(f.read().strip())

SITE_ID = localSettings['SITE_ID']

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = localSettings['DEBUG']

PROJECT_DIR = os.path.dirname(os.path.realpath(__file__))

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# TEMPLATE_DEBUG = DEBUG

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.DefaultStorageFinder',
    # 'dajaxice.finders.DajaxiceFinder',
)

# Make this unique, and don't share it with anybody.
with open('/data/secret_key.txt') as f:
    SECRET_KEY = f.read().strip()
# SECRET_KEY = 'A unique secret key'
# SECURITY WARNING: keep the secret key used in production secret!
# SECRET_KEY = '*(iy*i+rt4bq$bu9%3r0er8$01e^$gpv@jwljecm$96=ggb35='


ALLOWED_HOSTS = ['commeundessein.co', 'localhost', '127.0.0.1'] + localSettings['ALLOWED_HOSTS']

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'draw',
    # 'dajaxice',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.github',
    'paypal.standard.ipn',
    'anymail',
]

MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'CommeUnDessein.urls'


WSGI_APPLICATION = 'CommeUnDessein.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': os.path.join(PROJECT_DIR, 'comme-un-dessein.db'),
        # The following settings are not used with sqlite3:
        'USER': '',
        'PASSWORD': '',
        'HOST': '',                      # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',                      # Set to empty string for default.
    }
}


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = []
# [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
# ]


# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'fr-FR'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'

# --- Templates -- #

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Already defined Django-related contexts here

                # `allauth` needs this from django
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# ---- CUSTOM ---- #

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/var/www/example.com/static/"
STATIC_ROOT = os.path.join(PROJECT_DIR, 'static')

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(PROJECT_DIR, '../static'),
)

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/var/www/example.com/media/"
# MEDIA_ROOT = os.path.join(PROJECT_DIR, 'media')
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://example.com/media/", "http://media.example.com/"
MEDIA_URL = '/media/'


# APPEND_SLASH=False
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_BACKEND = localSettings['EMAIL_BACKEND']

DEFAULT_FROM_EMAIL = 'contact@commeundessein.co'

EMAIL_HOST = 'smtp.mailgun.org'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'postmaster@mg.commeundessein.co'
EMAIL_HOST_PASSWORD = localSettings['EMAIL_HOST_PASSWORD']
EMAIL_USE_TLS = True

ANYMAIL = {
    "MAILGUN_API_KEY": localSettings['MAILGUN_API_KEY'],
    "MAILGUN_SENDER_DOMAIN": 'mg.commeundessein.co',  # your Mailgun domain, if needed
    "MAILJET_API_KEY": localSettings['MAILJET_API_KEY'],
    "MAILJET_SECRET_KEY": localSettings['MAILJET_SECRET_KEY'],
    "SENDGRID_API_KEY": localSettings['SENDGRID_API_KEY'],
}

# DAJAXICE_MEDIA_PREFIX="dajaxice"

# ---- ALLAUTH ---- #

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # `allauth` specific authentication methods, such as login by e-mail
    'allauth.account.auth_backends.AuthenticationBackend',
)

LOGIN_REDIRECT_URL = '/'

ACCOUNT_EMAIL_SUBJECT_PREFIX = '[Comme un dessein] '
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
SOCIALACCOUNT_QUERY_EMAIL = True
ACCOUNT_EMAIL_REQUIRED = localSettings['ACCOUNT_EMAIL_REQUIRED']
ACCOUNT_EMAIL_VERIFICATION = localSettings['ACCOUNT_EMAIL_VERIFICATION'] # "mandatory", "optional"
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False

ACCOUNT_ADAPTER = 'CommeUnDessein.adapter.AccountAdapterCD'

# ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# Dictionary containing provider specific settings.
SOCIALACCOUNT_PROVIDERS = {
    'facebook': {
        'SCOPE': ['email', 'publish_actions'],
        'METHOD': 'js_sdk'  # instead of 'oauth2'
    },
    'google': {
        'SCOPE': ['https://www.googleapis.com/auth/userinfo.profile'],
        'AUTH_PARAMS': { 'access_type': 'online' }
    },
    'github': {
        'SCOPE': ['public_repo']
    }
}
