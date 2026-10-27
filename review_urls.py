from django.urls import path
from .review_views import review_screen

urlpatterns = [path("review/", review_screen, name="candidate-review")]
