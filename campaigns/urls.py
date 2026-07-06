from django.urls import path
from . import views

app_name = 'campaigns'

urlpatterns = [
    path('', views.CampaignListView.as_view(), name='list'),
    path('create/', views.CampaignCreateView.as_view(), name='create'),
    path('search/', views.CampaignSearchJsonView.as_view(), name='search'),
    path('<int:pk>/', views.CampaignDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CampaignUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.CampaignDeleteView.as_view(), name='delete'),
]
