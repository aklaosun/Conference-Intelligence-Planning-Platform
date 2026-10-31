"""Personal desktop demo: loopback-only service and private per-user SQLite data."""
import os,secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

if not os.environ.get('CCSE_DESKTOP_DATA_DIR'):
    raise ImproperlyConfigured('The desktop launcher must provide its private data directory.')
DESKTOP_DATA_DIR=Path(os.environ['CCSE_DESKTOP_DATA_DIR']).resolve()
DESKTOP_DATA_DIR.mkdir(parents=True,exist_ok=True)
DESKTOP_CONFIG=DESKTOP_DATA_DIR/'backend.env'
if not DESKTOP_CONFIG.exists():
    DESKTOP_CONFIG.write_text('# Private local backend configuration. Never share this file.\nGEMINI_API_KEY=\nGEMINI_MODEL=gemini-3.5-flash-lite\n',encoding='utf-8')
for line in DESKTOP_CONFIG.read_text(encoding='utf-8').splitlines():
    key,separator,value=line.partition('=')
    if separator and key.strip() in ['GEMINI_API_KEY','GEMINI_MODEL']:
        os.environ[key.strip()]=value.strip().strip('"').strip("'")
from .settings import *
LOCAL_DESKTOP=True
DEBUG=False
ALLOWED_HOSTS=['127.0.0.1','localhost','[::1]']
secret_path=DESKTOP_DATA_DIR/'django-secret.txt'
try:
    with secret_path.open('x',encoding='utf-8') as secret:secret.write(secrets.token_urlsafe(64))
    secret_path.chmod(0o600)
except FileExistsError:pass
SECRET_KEY=secret_path.read_text(encoding='utf-8')
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DESKTOP_DATA_DIR/'workspace.sqlite3',
    'OPTIONS':{'timeout':30}}}
MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')+1,'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_URL='/static/'
STATIC_ROOT=BASE_DIR/'staticfiles'
WHITENOISE_USE_FINDERS=True
WHITENOISE_AUTOREFRESH=True
EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend'
WORKSPACE_EMAIL_ENABLED=False
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Strict'
