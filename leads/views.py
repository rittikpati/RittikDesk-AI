import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import get_user_model
from core.mixins import OwnerFilterMixin
from workflows.services.engine import fire_trigger
from .models import Lead
from .forms import LeadForm

User = get_user_model()

SORT_MAP = {
    'newest': '-created_at',
    'oldest': 'created_at',
    'name_asc': 'lead_name',
    'name_desc': '-lead_name',
    'company_asc': 'company',
    'company_desc': '-company',
    'revenue_asc': 'expected_revenue',
    'revenue_desc': '-expected_revenue',
}

STATUS_CHOICES = ['New', 'Contacted', 'Qualified', 'Proposal Sent', 'Negotiation', 'Won', 'Lost']
PRIORITY_CHOICES = ['Low', 'Medium', 'High', 'Urgent']
SOURCE_CHOICES = ['Website', 'Referral', 'LinkedIn', 'Facebook', 'Instagram', 'Cold Email', 'Event', 'Other']


def apply_filters(qs, search, status_filter, priority_filter, source_filter, sort):
    if search:
        qs = qs.filter(
            Q(lead_name__icontains=search) |
            Q(company__icontains=search) |
            Q(contact_person__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
    if status_filter and status_filter in STATUS_CHOICES:
        qs = qs.filter(status=status_filter)
    if priority_filter and priority_filter in PRIORITY_CHOICES:
        qs = qs.filter(priority=priority_filter)
    if source_filter and source_filter in SOURCE_CHOICES:
        qs = qs.filter(source=source_filter)
    ordering = SORT_MAP.get(sort, '-created_at')
    qs = qs.order_by(ordering)
    return qs


class LeadListView(OwnerFilterMixin, ListView):
    model = Lead
    template_name = 'leads/lead_list.html'
    context_object_name = 'leads'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        status_filter = self.request.GET.get('status', '').strip()
        priority_filter = self.request.GET.get('priority', '').strip()
        source_filter = self.request.GET.get('source', '').strip()
        sort = self.request.GET.get('sort', 'newest')
        return apply_filters(qs, search, status_filter, priority_filter, source_filter, sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_leads'] = self.object_list.count()
        context['search_query'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['active_priority'] = self.request.GET.get('priority', '')
        context['active_source'] = self.request.GET.get('source', '')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        context['status_choices'] = STATUS_CHOICES
        context['priority_choices'] = PRIORITY_CHOICES
        context['source_choices'] = SOURCE_CHOICES
        context['sort_choices'] = [
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('name_asc', 'Name (A–Z)'),
            ('name_desc', 'Name (Z–A)'),
            ('company_asc', 'Company (A–Z)'),
            ('company_desc', 'Company (Z–A)'),
            ('revenue_asc', 'Revenue (Low)'),
            ('revenue_desc', 'Revenue (High)'),
        ]
        return context


class LeadCreateView(LoginRequiredMixin, CreateView):
    model = Lead
    form_class = LeadForm
    template_name = 'leads/lead_form.html'
    success_url = reverse_lazy('leads:list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        fire_trigger('lead_created', form.instance)
        messages.success(self.request, f'Lead "{form.instance.lead_name}" created successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Lead'
        return context


class LeadDetailView(OwnerFilterMixin, DetailView):
    model = Lead
    template_name = 'leads/lead_detail.html'
    context_object_name = 'lead'


class LeadUpdateView(OwnerFilterMixin, UpdateView):
    model = Lead
    form_class = LeadForm
    template_name = 'leads/lead_form.html'
    success_url = reverse_lazy('leads:list')

    def form_valid(self, form):
        old_status = self.get_object().status
        response = super().form_valid(form)
        fire_trigger('lead_updated', form.instance)
        new_status = form.instance.status
        if old_status != new_status:
            if new_status == 'Qualified':
                fire_trigger('lead_qualified', form.instance)
            elif new_status == 'Won':
                fire_trigger('lead_won', form.instance)
            elif new_status == 'Lost':
                fire_trigger('lead_lost', form.instance)
        messages.success(self.request, f'Lead "{form.instance.lead_name}" updated successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Lead'
        context['is_update'] = True
        return context


class LeadDeleteView(OwnerFilterMixin, DeleteView):
    model = Lead
    template_name = 'leads/lead_confirm_delete.html'
    success_url = reverse_lazy('leads:list')
    context_object_name = 'lead'

    def form_valid(self, form):
        messages.success(self.request, f'Lead "{self.object.lead_name}" deleted successfully.')
        return super().form_valid(form)


class LeadSearchJsonView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get('search', '').strip()
        status_filter = request.GET.get('status', '').strip()
        priority_filter = request.GET.get('priority', '').strip()
        source_filter = request.GET.get('source', '').strip()
        sort = request.GET.get('sort', 'newest')
        qs = Lead.objects.filter(owner=request.user).select_related('owner', 'assigned_user')
        qs = apply_filters(qs, search, status_filter, priority_filter, source_filter, sort)

        data = []
        for lead in qs:
            assigned = ''
            if lead.assigned_user:
                assigned = lead.assigned_user.get_full_name() or lead.assigned_user.email
            data.append({
                'id': lead.pk,
                'lead_name': lead.lead_name,
                'company': lead.company or '',
                'contact_person': lead.contact_person or '',
                'email': lead.email or '',
                'phone': lead.phone or '',
                'status': lead.status,
                'priority': lead.priority,
                'source': lead.source,
                'expected_revenue': str(lead.expected_revenue) if lead.expected_revenue else '',
                'assigned_user': assigned,
                'detail_url': reverse('leads:detail', args=[lead.pk]),
                'update_url': reverse('leads:update', args=[lead.pk]),
                'delete_url': reverse('leads:delete', args=[lead.pk]),
            })

        return JsonResponse({
            'leads': data,
            'count': len(data),
            'search': search,
            'status': status_filter,
            'priority': priority_filter,
            'source': source_filter,
            'sort': sort,
        })


class LeadBulkDeleteView(OwnerFilterMixin, View):
    def post(self, request):
        ids = request.POST.getlist('ids')
        leads = Lead.objects.filter(owner=request.user, pk__in=ids)
        count = leads.count()
        leads.delete()
        messages.success(request, f'{count} lead(s) deleted successfully.')
        return JsonResponse({'deleted': count})


class LeadExportView(OwnerFilterMixin, View):
    def get(self, request):
        ids = request.GET.get('ids', '')
        qs = self.get_queryset()
        if ids:
            id_list = [int(i) for i in ids.split(',') if i.isdigit()]
            qs = qs.filter(pk__in=id_list)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="leads.csv"'
        writer = csv.writer(response)
        writer.writerow(['Lead Name', 'Company', 'Contact Person', 'Email', 'Phone',
                         'Status', 'Priority', 'Source', 'Expected Revenue', 'Assigned User', 'Notes'])
        for lead in qs:
            assigned = lead.assigned_user.get_full_name() or lead.assigned_user.email if lead.assigned_user else ''
            writer.writerow([
                lead.lead_name, lead.company, lead.contact_person, lead.email, lead.phone,
                lead.status, lead.priority, lead.source,
                str(lead.expected_revenue) if lead.expected_revenue else '',
                assigned, lead.notes,
            ])
        return response
