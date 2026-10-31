from django.urls import path
from . import platform_api as api
urlpatterns=[
    path('session/',api.session),path('login/',api.sign_in),path('logout/',api.sign_out),
    path('overview/',api.overview),path('catalog/',api.catalog),path('catalog/<int:pk>/',api.detail),
    path('plans/',api.plans),path('plans/<int:pk>/',api.plan),path('outcomes/<int:pk>/',api.outcome),
    path('criteria/',api.criteria),path('ratings/<int:pk>/',api.rating),path('deadlines/',api.deadlines),
    path('reports/',api.reports),path('team/',api.team),path('invitations/<str:token>/',api.invitation),
    path('reports/export/',api.export_planning),path('subscriptions/',api.subscriptions),
    path('desktop-bootstrap/',api.desktop_bootstrap),path('local-settings/',api.local_settings),
]
