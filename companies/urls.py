from django.urls import path
from . import views

app_name = 'companies'

urlpatterns = [
    path('', views.CompanyListView.as_view(), name='list'),
    path('create/', views.CompanyCreateView.as_view(), name='create'),
    path('search/', views.CompanySearchJsonView.as_view(), name='search'),
    path('import/', views.CompanyImportView.as_view(), name='import'),
    path('export/csv/', views.CompanyExportCSVView.as_view(), name='export_csv'),
    path('export/xlsx/', views.CompanyExportXLSXView.as_view(), name='export_xlsx'),
    path('export/pdf/', views.CompanyExportPDFView.as_view(), name='export_pdf'),
    path('bulk-delete/', views.CompanyBulkDeleteView.as_view(), name='bulk_delete'),
    path('bulk-update/', views.CompanyBulkUpdateView.as_view(), name='bulk_update'),
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.CompanyUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.CompanyDeleteView.as_view(), name='delete'),
]
