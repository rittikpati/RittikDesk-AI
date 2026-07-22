from django.urls import path
from . import views

app_name = 'deals'

urlpatterns = [
    path('', views.DealListView.as_view(), name='list'),
    path('create/', views.DealCreateView.as_view(), name='create'),
    path('search/', views.DealSearchJsonView.as_view(), name='search'),
    path('export/csv/', views.DealExportCSVView.as_view(), name='export_csv'),
    path('export/xlsx/', views.DealExportXLSXView.as_view(), name='export_xlsx'),
    path('export/pdf/', views.DealExportPDFView.as_view(), name='export_pdf'),
    path('bulk-delete/', views.DealBulkDeleteView.as_view(), name='bulk_delete'),
    path('bulk-update/', views.DealBulkUpdateView.as_view(), name='bulk_update'),
    path('kanban/', views.DealKanbanView.as_view(), name='kanban'),
    path('kanban/update/', views.DealKanbanUpdateView.as_view(), name='kanban_update'),
    path('<int:pk>/', views.DealDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.DealUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.DealDeleteView.as_view(), name='delete'),
]
