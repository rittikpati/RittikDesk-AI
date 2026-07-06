from django.urls import path
from . import views

app_name = 'leads'

urlpatterns = [
    path('', views.LeadListView.as_view(), name='list'),
    path('create/', views.LeadCreateView.as_view(), name='create'),
    path('search/', views.LeadSearchJsonView.as_view(), name='search'),
    path('export/', views.LeadExportView.as_view(), name='export'),
    path('bulk-delete/', views.LeadBulkDeleteView.as_view(), name='bulk_delete'),
    path('<int:pk>/', views.LeadDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.LeadUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.LeadDeleteView.as_view(), name='delete'),
]
