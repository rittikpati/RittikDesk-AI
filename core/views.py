from django.views.generic import TemplateView
from django.http import JsonResponse


class LandingView(TemplateView):
    template_name = 'core/landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'RittikDesk AI — AI-Powered CRM & Campaign Platform'
        return context


class HealthCheckView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'healthy', 'version': '1.0.0'})
