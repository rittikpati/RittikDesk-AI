from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from core.mixins import OwnerFilterMixin
from .models import Campaign
from .forms import CampaignForm


class CampaignListView(OwnerFilterMixin, ListView):
    model = Campaign
    template_name = 'campaigns/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(subject__icontains=search)
            )
        if status_filter and status_filter in ['Draft', 'Scheduled', 'Sent']:
            qs = qs.filter(status=status_filter)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_campaigns'] = self.object_list.count()
        context['search_query'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['status_choices'] = ['Draft', 'Scheduled', 'Sent']
        return context


class CampaignCreateView(LoginRequiredMixin, CreateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'
    success_url = reverse_lazy('campaigns:list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Campaign "{form.instance.name}" created successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Campaign'
        return context


class CampaignDetailView(OwnerFilterMixin, DetailView):
    model = Campaign
    template_name = 'campaigns/campaign_detail.html'
    context_object_name = 'campaign'


class CampaignUpdateView(OwnerFilterMixin, UpdateView):
    model = Campaign
    form_class = CampaignForm
    template_name = 'campaigns/campaign_form.html'
    success_url = reverse_lazy('campaigns:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Campaign "{form.instance.name}" updated successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Campaign'
        context['is_update'] = True
        return context


class CampaignDeleteView(OwnerFilterMixin, DeleteView):
    model = Campaign
    template_name = 'campaigns/campaign_confirm_delete.html'
    success_url = reverse_lazy('campaigns:list')
    context_object_name = 'campaign'

    def form_valid(self, form):
        messages.success(self.request, f'Campaign "{self.object.name}" deleted successfully.')
        return super().form_valid(form)


class CampaignSearchJsonView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '').strip()
        qs = Campaign.objects.filter(owner=request.user)
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(subject__icontains=search)
            )
        if status_filter and status_filter in ['Draft', 'Scheduled', 'Sent']:
            qs = qs.filter(status=status_filter)
        qs = qs.order_by('-created_at')

        data = []
        for c in qs:
            data.append({
                'id': c.pk,
                'name': c.name,
                'subject': c.subject,
                'body': c.body,
                'status': c.status,
                'scheduled_at': c.scheduled_at.strftime('%b %d, %Y %I:%M %p') if c.scheduled_at else '',
                'detail_url': reverse('campaigns:detail', args=[c.pk]),
                'update_url': reverse('campaigns:update', args=[c.pk]),
                'delete_url': reverse('campaigns:delete', args=[c.pk]),
            })

        return JsonResponse({
            'campaigns': data,
            'count': len(data),
            'search': search,
            'status': status_filter,
        })
