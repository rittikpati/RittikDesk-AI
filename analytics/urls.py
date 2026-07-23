from django.urls import path

from .views import PipelineAnalyticsView

app_name = 'analytics'

urlpatterns = [
    path('', PipelineAnalyticsView.as_view(), name='pipeline'),
]
