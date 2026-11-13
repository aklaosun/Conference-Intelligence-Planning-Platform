"""Authenticated browser workspace on loopback; shared hosting uses production_settings."""
import os,secrets
from pathlib import Path
from .settings import *

LOCAL_DESKTOP=False
WEB_WORKSPACE=True
DEBUG=False
WEB_DATA_DIR=Path(os.environ.get('CCSE_WEB_DATA_DIR',str(BASE_DIR.parent/'.web-data'))).resolve()
WEB_DATA_DIR.mkdir(parents=True,exist_ok=True)
WEB_AI_CONFIG=WEB_DATA_DIR/'backend.env'
if not WEB_AI_CONFIG.exists():
    WEB_AI_CONFIG.write_text('# Private browser workspace AI settings. Never commit or share.\n',encoding='utf-8')
for line in WEB_AI_CONFIG.read_text(encoding='utf-8').splitlines():
    key,separator,value=line.partition('=')
    if separator and key.strip() in ['GEMINI_API_KEY','GEMINI_MODEL']:
        os.environ[key.strip()]=value.strip()
secret_file=WEB_DATA_DIR/'django-secret.txt'
try:
    with secret_file.open('x',encoding='utf-8') as handle:handle.write(secrets.token_urlsafe(64))
except FileExistsError:pass
SECRET_KEY=secret_file.read_text(encoding='utf-8')
ALLOWED_HOSTS=['127.0.0.1','localhost','testserver']
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':WEB_DATA_DIR/'workspace.sqlite3','OPTIONS':{'timeout':30}}}
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')+1,'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
WHITENOISE_USE_FINDERS=True
WHITENOISE_AUTOREFRESH=True
EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend'
WORKSPACE_EMAIL_ENABLED=False
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
SESSION_COOKIE_AGE=60*60*8
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_REFERRER_POLICY='same-origin'
LOGIN_REDIRECT_URL='/app/'
LOGOUT_REDIRECT_URL='/app/'
