import hashlib
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone

ROLE_CHOICES=[('viewer','Viewer'),('contributor','Contributor'),('coordinator','Coordinator')]
ROLE_GROUPS={'viewer':'Viewers','contributor':'Contributors','coordinator':'Coordinators'}

class AccessInvitation(models.Model):
    email=models.EmailField()
    role=models.CharField(max_length=20,choices=ROLE_CHOICES)
    token_hash=models.CharField(max_length=64,unique=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True)
    revoked_at=models.DateTimeField(null=True)
    @property
    def usable(self):return not self.used_at and not self.revoked_at and self.expires_at>timezone.now()
    @staticmethod
    def digest(token):return hashlib.sha256(token.encode()).hexdigest()
    @classmethod
    def issue(cls,*,email,role,user):
        if role not in ROLE_GROUPS:raise ValueError('Unknown access role.')
        token=secrets.token_urlsafe(32)
        invitation=cls.objects.create(email=email.strip().lower(),role=role,token_hash=cls.digest(token),
            created_by=user,expires_at=timezone.now()+timezone.timedelta(days=3))
        return invitation,token

class LoginThrottle(models.Model):
    key=models.CharField(max_length=64,unique=True)
    failures=models.PositiveIntegerField(default=0)
    window_started=models.DateTimeField(default=timezone.now)
