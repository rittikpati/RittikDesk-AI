from django.urls import path
from . import views

app_name = 'emails'

urlpatterns = [
    # SMTP Config
    path('smtp/', views.SMTPConfigView.as_view(), name='smtp_config'),
    path('smtp/save/', views.SMTPConfigSaveView.as_view(), name='smtp_save'),
    path('smtp/test/', views.SMTPConfigTestView.as_view(), name='smtp_test'),
    path('smtp/diagnostic/', views.SMTPConfigDiagnosticView.as_view(), name='smtp_diagnostic'),
    path('smtp/reset/', views.SMTPConfigResetView.as_view(), name='smtp_reset'),

    # Compose / Send
    path('compose/', views.ComposeEmailView.as_view(), name='compose'),
    path('reply/<int:pk>/', views.ReplyEmailView.as_view(), name='reply'),

    # Sent Mail
    path('', views.SentEmailListView.as_view(), name='sent'),
    path('<int:pk>/', views.EmailDetailView.as_view(), name='detail'),
    path('<int:pk>/delete/', views.EmailDeleteView.as_view(), name='delete'),
    path('<int:pk>/cancel/', views.EmailCancelView.as_view(), name='cancel'),
    path('<int:pk>/retry/', views.EmailRetryView.as_view(), name='retry'),

    # Drafts
    path('drafts/', views.DraftListView.as_view(), name='drafts'),

    # Templates
    path('templates/', views.TemplateListView.as_view(), name='templates'),
    path('templates/create/', views.TemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/edit/', views.TemplateUpdateView.as_view(), name='template_update'),
    path('templates/<int:pk>/delete/', views.TemplateDeleteView.as_view(), name='template_delete'),

    # AJAX
    path('api/templates/<int:pk>/', views.TemplateJsonView.as_view(), name='template_json'),
    path('api/stats/', views.EmailStatsJsonView.as_view(), name='stats_json'),
]
