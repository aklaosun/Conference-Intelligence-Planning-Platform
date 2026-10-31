"""Bundled Electron backend. Always binds loopback; never exposes a network listener."""
import json,os,secrets,sys
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer,WSGIRequestHandler,make_server

if not getattr(sys,'frozen',False):sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ccse-conference-platform'))
os.environ['DJANGO_SETTINGS_MODULE']='ccse_platform.desktop_settings'
os.environ['CCSE_DESKTOP_BOOTSTRAP_TOKEN']=secrets.token_urlsafe(32)
import django
django.setup()
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from conferences.models import Conference

def initialize():
    call_command('migrate',interactive=False,verbosity=0)
    call_command('setup_platform',verbosity=0)
    username='desktop-owner'
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(username=username,password=secrets.token_urlsafe(48),first_name='Local Demo',last_name='Owner')
    marker=settings.DESKTOP_DATA_DIR/'catalog-seeded-v1'
    if not marker.exists():
        seed=Path(os.environ['CCSE_DESKTOP_SEED'])
        if not Conference.objects.exists():call_command('loaddata',str(seed),verbosity=0)
        marker.write_text('Real spreadsheet catalog initialized.\n',encoding='utf-8')

class ThreadedServer(ThreadingMixIn,WSGIServer):daemon_threads=True
class QuietHandler(WSGIRequestHandler):
    def log_message(self,format,*args):pass

if __name__=='__main__':
    initialize()
    with make_server('127.0.0.1',0,get_wsgi_application(),server_class=ThreadedServer,handler_class=QuietHandler) as server:
        print('CCSE_READY '+json.dumps({'port':server.server_port,'token':os.environ['CCSE_DESKTOP_BOOTSTRAP_TOKEN']}),flush=True)
        server.serve_forever()
