from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

handler404 = 'core.views.handler404'
handler403 = 'core.views.handler403'
handler500 = 'core.views.handler500'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    
    path('contacts/', include('contacts.urls')),
    path('leads/', include('leads.urls')),
    path('campaigns/', include('campaigns.urls')),
    path('assistant/', include('assistant.urls')),
    path('analytics/', include('analytics.urls')),
    path('tasks/', include('tasks.urls')),
    path('calendar/', include('calendars.urls')),
    path('api/', include('accounts.api_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
