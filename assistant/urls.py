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
    path('<int:pk>/stream/', views.ChatMessageStreamView.as_view(), name='message_stream'),
    path('<int:pk>/pin/', views.ChatPinToggleView.as_view(), name='pin'),
    path('message/<int:pk>/edit/', views.ChatEditMessageView.as_view(), name='edit_message'),
    path('<int:pk>/move-category/', views.ConversationMoveCategoryView.as_view(), name='move_category'),
    path('category/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('category/<int:pk>/rename/', views.CategoryRenameView.as_view(), name='category_rename'),
    path('category/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
]
