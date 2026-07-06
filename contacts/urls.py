from django.urls import path
from . import views

app_name = 'contacts'

urlpatterns = [
    path('', views.ContactListView.as_view(), name='list'),
    path('create/', views.ContactCreateView.as_view(), name='create'),
    path('search/', views.ContactSearchJsonView.as_view(), name='search'),
    path('export/', views.ContactExportView.as_view(), name='export'),
    path('bulk-delete/', views.ContactBulkDeleteView.as_view(), name='bulk_delete'),
    path('<int:pk>/', views.ContactDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ContactUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.ContactDeleteView.as_view(), name='delete'),
]
