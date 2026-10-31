"""Shared HTTPS deployment; never uses the local demo database or demo login."""
import os
from urllib.parse import urlsplit
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .settings import *

DEBUG=False
SECRET_KEY=os.environ.get('DJANGO_SECRET_KEY','')
if len(SECRET_KEY)<50 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Set a private DJANGO_SECRET_KEY of at least 50 characters.')
PUBLIC_BASE_URL=os.environ.get('PUBLIC_BASE_URL','').rstrip('/')
public=urlsplit(PUBLIC_BASE_URL)
if public.scheme!='https' or not public.hostname or public.username or public.password or public.path or public.query or public.fragment:
    raise ImproperlyConfigured('PUBLIC_BASE_URL must be your HTTPS server origin, without a path or credentials.')
ALLOWED_HOSTS=[public.hostname]+[h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS','').split(',') if h.strip()]
if '*' in ALLOWED_HOSTS:raise ImproperlyConfigured('Wildcard ALLOWED_HOSTS are not allowed.')
CSRF_TRUSTED_ORIGINS=[PUBLIC_BASE_URL]
database=os.environ.get('DATABASE_URL','')
if not database:raise ImproperlyConfigured('Configure a persistent PostgreSQL DATABASE_URL.')
DATABASES={'default':dj_database_url.parse(database,conn_max_age=60,conn_health_checks=True,
    ssl_require=os.environ.get('DATABASE_SSL_REQUIRE','1')=='1')}
if DATABASES['default']['ENGINE']!='django.db.backends.postgresql':
    raise ImproperlyConfigured('Shared workspaces require PostgreSQL; local SQLite is only for development.')
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')+1,'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
    'staticfiles':{'BACKEND':'whitenoise.storage.CompressedStaticFilesStorage'}}
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=3600
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
if os.environ.get('DJANGO_TRUST_PROXY','0')=='1':
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO','https')
DATA_UPLOAD_MAX_MEMORY_SIZE=2_000_000
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST=os.environ.get('EMAIL_HOST','')
EMAIL_PORT=int(os.environ.get('EMAIL_PORT','587'))
EMAIL_HOST_USER=os.environ.get('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD=os.environ.get('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS=os.environ.get('EMAIL_USE_TLS','1')=='1'
EMAIL_TIMEOUT=20
DEFAULT_FROM_EMAIL=os.environ.get('DEFAULT_FROM_EMAIL','')
WORKSPACE_EMAIL_ENABLED=os.environ.get('WORKSPACE_EMAIL_ENABLED','0')=='1'
