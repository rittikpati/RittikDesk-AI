import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from core.mixins import OwnerFilterMixin
from .models import Contact
from .forms import ContactForm


SORT_MAP = {
    'newest': '-created_at',
    'oldest': 'created_at',
    'name_asc': 'full_name',
    'name_desc': '-full_name',
    'company_asc': 'company',
    'company_desc': '-company',
}
TAG_CHOICES = ['Client', 'Lead', 'Prospect', 'VIP', 'Partner']


def apply_filters(qs, search, tag, sort):
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(company__icontains=search) |
            Q(phone__icontains=search)
        )
    if tag and tag in TAG_CHOICES:
        qs = qs.filter(tags__icontains=tag)
    ordering = SORT_MAP.get(sort, '-created_at')
    qs = qs.order_by(ordering)
    return qs


class ContactListView(OwnerFilterMixin, ListView):
    model = Contact
    template_name = 'contacts/contact_list.html'
    context_object_name = 'contacts'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        tag = self.request.GET.get('tag', '').strip()
        sort = self.request.GET.get('sort', 'newest')
        return apply_filters(qs, search, tag, sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_contacts'] = self.object_list.count()
        context['search_query'] = self.request.GET.get('search', '')
        context['active_tag'] = self.request.GET.get('tag', '')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        context['tag_choices'] = TAG_CHOICES
        context['sort_choices'] = [
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('name_asc', 'Name (A–Z)'),
            ('name_desc', 'Name (Z–A)'),
            ('company_asc', 'Company (A–Z)'),
            ('company_desc', 'Company (Z–A)'),
        ]
        return context


class ContactCreateView(LoginRequiredMixin, CreateView):
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_form.html'
    success_url = reverse_lazy('contacts:list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Contact "{form.instance.full_name}" created successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Contact'
        return context


class ContactDetailView(OwnerFilterMixin, DetailView):
    model = Contact
    template_name = 'contacts/contact_detail.html'
    context_object_name = 'contact'


class ContactUpdateView(OwnerFilterMixin, UpdateView):
    model = Contact
    form_class = ContactForm
    template_name = 'contacts/contact_form.html'
    success_url = reverse_lazy('contacts:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Contact "{form.instance.full_name}" updated successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Contact'
        context['is_update'] = True
        return context


class ContactDeleteView(OwnerFilterMixin, DeleteView):
    model = Contact
    template_name = 'contacts/contact_confirm_delete.html'
    success_url = reverse_lazy('contacts:list')
    context_object_name = 'contact'

    def form_valid(self, form):
        messages.success(self.request, f'Contact "{self.object.full_name}" deleted successfully.')
        return super().form_valid(form)


class ContactSearchJsonView(LoginRequiredMixin, View):
    def get(self, request):
        search = request.GET.get('search', '').strip()
        tag = request.GET.get('tag', '').strip()
        sort = request.GET.get('sort', 'newest')
        qs = Contact.objects.filter(owner=request.user)
        qs = apply_filters(qs, search, tag, sort)

        data = []
        for c in qs:
            data.append({
                'id': c.pk,
                'full_name': c.full_name,
                'email': c.email or '',
                'company': c.company or '',
                'phone': c.phone or '',
                'job_title': c.job_title or '',
                'tags': c.tag_list(),
                'avatar_initials': c.full_name[:2].upper(),
                'detail_url': reverse('contacts:detail', args=[c.pk]),
                'update_url': reverse('contacts:update', args=[c.pk]),
                'delete_url': reverse('contacts:delete', args=[c.pk]),
            })

        return JsonResponse({
            'contacts': data,
            'count': len(data),
            'search': search,
            'tag': tag,
            'sort': sort,
        })


class ContactBulkDeleteView(OwnerFilterMixin, View):
    def post(self, request):
        ids = request.POST.getlist('ids')
        contacts = Contact.objects.filter(owner=request.user, pk__in=ids)
        count = contacts.count()
        contacts.delete()
        messages.success(request, f'{count} contact(s) deleted successfully.')
        return JsonResponse({'deleted': count})


class ContactExportView(OwnerFilterMixin, View):
    def get(self, request):
        ids = request.GET.get('ids', '')
        qs = self.get_queryset()
        if ids:
            id_list = [int(i) for i in ids.split(',') if i.isdigit()]
            qs = qs.filter(pk__in=id_list)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contacts.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Phone', 'Company', 'Job Title', 'Tags', 'Notes'])
        for c in qs:
            writer.writerow([c.full_name, c.email, c.phone, c.company, c.job_title, c.tags, c.notes])
        return response
