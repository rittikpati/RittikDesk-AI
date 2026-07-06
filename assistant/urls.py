from django.urls import path
from . import views

app_name = 'assistant'

urlpatterns = [
    path('', views.ChatListView.as_view(), name='list'),
    path('new/', views.ChatCreateView.as_view(), name='new'),
    path('<int:pk>/', views.ChatDetailView.as_view(), name='chat'),
    path('<int:pk>/delete/', views.ChatDeleteView.as_view(), name='delete'),
    path('<int:pk>/rename/', views.ChatRenameView.as_view(), name='rename'),
    path('<int:pk>/export/', views.ChatExportView.as_view(), name='export'),
    path('<int:pk>/message/', views.ChatMessageView.as_view(), name='message'),
]
