from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView


@method_decorator(login_required, name='dispatch')
class DashboardHomeView(TemplateView):
    template_name = 'dashboard/home.html'
