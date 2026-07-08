from django.views.generic import TemplateView
from django.http import JsonResponse
from django.shortcuts import render


def handler404(request, exception):
    return render(request, '404.html', status=404)


def handler403(request, exception):
    return render(request, '403.html', status=403)


def handler500(request):
    return render(request, '500.html', status=500)


class LandingView(TemplateView):
    template_name = 'core/landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'RittikDesk AI — AI-Powered CRM & Campaign Platform'
        return context


class HealthCheckView(TemplateView):
    def get(self, request, *args, **kwargs):
        return JsonResponse({'status': 'healthy', 'version': '1.0.0'})
