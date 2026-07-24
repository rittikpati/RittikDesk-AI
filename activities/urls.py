from django.urls import path
from . import views

app_name = 'activities'

urlpatterns = [
    path('', views.ActivityTimelineView.as_view(), name='timeline'),
    path('json/', views.ActivityJSONView.as_view(), name='json'),
]
