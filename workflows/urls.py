from django.urls import path
from . import views

app_name = 'workflows'

urlpatterns = [
    # Workflow CRUD
    path('', views.WorkflowListView.as_view(), name='list'),
    path('create/', views.WorkflowCreateView.as_view(), name='create'),
    path('<int:pk>/', views.WorkflowDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.WorkflowUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.WorkflowDeleteView.as_view(), name='delete'),
    path('<int:pk>/toggle/', views.WorkflowToggleView.as_view(), name='toggle'),

    # Workflow Actions (inline JSON)
    path('<int:workflow_pk>/actions/create/', views.WorkflowActionCreateView.as_view(), name='action_create'),
    path('<int:workflow_pk>/actions/<int:pk>/edit/', views.WorkflowActionUpdateView.as_view(), name='action_update'),
    path('<int:workflow_pk>/actions/<int:pk>/delete/', views.WorkflowActionDeleteView.as_view(), name='action_delete'),

    # Execution logs
    path('logs/<int:pk>/', views.WorkflowExecutionLogDetailView.as_view(), name='log_detail'),

    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='notification_read'),
    path('notifications/read-all/', views.NotificationMarkAllReadView.as_view(), name='notification_read_all'),
    path('notifications/<int:pk>/clear/', views.NotificationClearView.as_view(), name='notification_clear'),
    path('notifications/clear-all/', views.NotificationClearAllView.as_view(), name='notification_clear_all'),
]
