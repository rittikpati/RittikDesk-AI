import json
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, View, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
from core.mixins import OwnerFilterMixin
from .models import SMTPConfig, EmailMessage, EmailAttachment, EmailTemplate
from .forms import SMTPConfigForm, ComposeEmailForm, EmailTemplateForm
from .services import test_smtp_connection, send_email_message, diagnostic_smtp_connection

logger = logging.getLogger(__name__)


SORT_MAP = {
    'newest': '-created_at',
    'oldest': 'created_at',
    'subject_asc': 'subject',
    'subject_desc': '-subject',
    'status': 'status',
    'sent_asc': 'sent_at',
    'sent_desc': '-sent_at',
}
STATUS_CHOICES = ['draft', 'queued', 'sent', 'delivered', 'failed', 'cancelled', 'scheduled']


def apply_filters(qs, search, status, sort):
    if search:
        qs = qs.filter(
            Q(subject__icontains=search) |
            Q(to_emails__icontains=search) |
            Q(body_plain__icontains=search)
        )
    if status in STATUS_CHOICES:
        qs = qs.filter(status=status)
    ordering = SORT_MAP.get(sort, '-created_at')
    qs = qs.order_by(ordering)
    return qs


# ──────────────────────────────────────────────
#  SMTP Configuration
# ──────────────────────────────────────────────

class SMTPConfigView(LoginRequiredMixin, TemplateView):
    template_name = 'emails/smtp_config.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = SMTPConfig.objects.filter(owner=self.request.user).first()
        user = self.request.user
        if config:
            context['form'] = SMTPConfigForm(instance=config, user=user)
            context['config'] = config
        else:
            context['form'] = SMTPConfigForm(user=user)
        context['debug'] = settings.DEBUG
        return context


class SMTPConfigSaveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        config = SMTPConfig.objects.filter(owner=request.user).first()
        if config:
            form = SMTPConfigForm(request.POST, instance=config, user=request.user)
        else:
            form = SMTPConfigForm(request.POST, user=request.user)
        if form.is_valid():
            config = form.save(commit=False)
            config.owner = request.user
            config.save()
            messages.success(request, 'SMTP configuration saved successfully.')
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, f'{field}: {err}')
        return HttpResponseRedirect(reverse('emails:smtp_config'))


class SMTPConfigTestView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        config = get_object_or_404(SMTPConfig, owner=request.user)
        success, msg = test_smtp_connection(config)
        if success:
            config.is_verified = True
            config.last_tested = timezone.now()
            config.save(update_fields=['is_verified', 'last_tested'])
        return JsonResponse({'success': success, 'message': msg})


class SMTPConfigDiagnosticView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        if not settings.DEBUG:
            return HttpResponseForbidden('Diagnostic endpoint only available in DEBUG mode.')
        config = SMTPConfig.objects.filter(owner=request.user).first()
        if not config:
            return JsonResponse({'steps': [], 'error': 'No SMTP configuration found.'})
        steps = diagnostic_smtp_connection(config)
        return JsonResponse({'steps': steps})


class SMTPConfigResetView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        SMTPConfig.objects.filter(owner=request.user).delete()
        messages.success(request, 'SMTP configuration has been reset.')
        return HttpResponseRedirect(reverse('emails:smtp_config'))


# ──────────────────────────────────────────────
#  Email Compose / Send
# ──────────────────────────────────────────────

class ComposeEmailView(LoginRequiredMixin, CreateView):
    model = EmailMessage
    form_class = ComposeEmailForm
    template_name = 'emails/compose.html'
    success_url = reverse_lazy('emails:sent')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        smtp_config = SMTPConfig.objects.filter(owner=self.request.user).first()
        form.instance.smtp_config = smtp_config
        action = self.request.POST.get('action', 'send')
        if action == 'draft':
            form.instance.is_draft = True
            form.instance.status = 'draft'
        else:
            form.instance.is_draft = False
            if form.instance.scheduled_time:
                form.instance.status = 'scheduled'
            else:
                form.instance.status = 'queued'
        response = super().form_valid(form)
        self._handle_attachments(form.instance, self.request.FILES)
        if action == 'send' and not form.instance.scheduled_time:
            success, error = send_email_message(form.instance)
            if success:
                messages.success(self.request, 'Email sent successfully.')
            else:
                messages.error(self.request, f'Failed to send: {error}')
        elif action == 'schedule':
            messages.success(self.request, 'Email scheduled successfully.')
        else:
            messages.success(self.request, 'Draft saved.')
        return response

    def _handle_attachments(self, email, files):
        for key, uploaded in files.items():
            if key.startswith('attachments'):
                EmailAttachment.objects.create(
                    email=email,
                    file=uploaded,
                    original_filename=uploaded.name,
                    file_size=uploaded.size,
                    content_type=uploaded.content_type or '',
                )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Compose Email'
        context['templates'] = EmailTemplate.objects.filter(
            Q(owner=self.request.user) | Q(is_shared=True)
        )
        user = self.request.user
        qs = SMTPConfig.objects.filter(owner=user)
        has_smtp = qs.exists()
        if not has_smtp:
            total = SMTPConfig.objects.count()
            all_configs = list(SMTPConfig.objects.select_related('owner').all().values('id', 'owner_id', 'owner__username', 'host'))
            import sys
            print(f'[DEBUG COMPOSE] user_id={user.id} email={user.email!r} username={user.username!r} has_smtp={has_smtp} total_configs={total} all={all_configs}', flush=True)
        else:
            config = qs.first()
            print(f'[DEBUG COMPOSE] user_id={user.id} has_smtp=True config_id={config.id} owner_id={config.owner_id}', flush=True)
        context['has_smtp'] = has_smtp
        return context


class ReplyEmailView(LoginRequiredMixin, CreateView):
    model = EmailMessage
    form_class = ComposeEmailForm
    template_name = 'emails/compose.html'
    success_url = reverse_lazy('emails:sent')

    def get_initial(self):
        initial = super().get_initial()
        original = get_object_or_404(EmailMessage, pk=self.kwargs['pk'], owner=self.request.user)
        initial['to_emails'] = original.to_emails
        initial['subject'] = f'Re: {original.subject}'
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        smtp_config = SMTPConfig.objects.filter(owner=self.request.user).first()
        form.instance.smtp_config = smtp_config
        action = self.request.POST.get('action', 'send')
        original_pk = self.kwargs.get('pk')
        msg_ref = ''
        if original_pk:
            original = EmailMessage.objects.filter(pk=original_pk, owner=self.request.user).first()
            if original:
                msg_ref = f'\n\n--- Original Message ---\nFrom: {original.owner.email}\nSubject: {original.subject}\nDate: {original.created_at}\n\n{original.body_plain or original.body_html or ""}'
                form.instance.body_plain = (form.instance.body_plain or '') + msg_ref
        if action == 'draft':
            form.instance.is_draft = True
            form.instance.status = 'draft'
        else:
            form.instance.is_draft = False
            if form.instance.scheduled_time:
                form.instance.status = 'scheduled'
            else:
                form.instance.status = 'queued'
        response = super().form_valid(form)
        self._handle_attachments(form.instance, self.request.FILES)
        if action == 'send' and not form.instance.scheduled_time:
            success, error = send_email_message(form.instance)
            if success:
                messages.success(self.request, 'Reply sent successfully.')
            else:
                messages.error(self.request, f'Failed to send: {error}')
        elif action == 'schedule':
            messages.success(self.request, 'Reply scheduled.')
        else:
            messages.success(self.request, 'Draft saved.')
        return response

    def _handle_attachments(self, email, files):
        for key, uploaded in files.items():
            if key.startswith('attachments'):
                EmailAttachment.objects.create(
                    email=email,
                    file=uploaded,
                    original_filename=uploaded.name,
                    file_size=uploaded.size,
                    content_type=uploaded.content_type or '',
                )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Reply to Email'
        context['templates'] = EmailTemplate.objects.filter(
            Q(owner=self.request.user) | Q(is_shared=True)
        )
        context['has_smtp'] = SMTPConfig.objects.filter(owner=self.request.user).exists()
        return context


# ──────────────────────────────────────────────
#  Sent / Inbox
# ──────────────────────────────────────────────

class SentEmailListView(OwnerFilterMixin, ListView):
    model = EmailMessage
    template_name = 'emails/sent_list.html'
    context_object_name = 'emails'
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_draft=False).select_related('smtp_config')
        search = self.request.GET.get('search', '').strip()
        status = self.request.GET.get('status', '').strip()
        sort = self.request.GET.get('sort', 'newest')
        return apply_filters(qs, search, status, sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        context['status_choices'] = EmailMessage.STATUS_CHOICES
        context['sort_choices'] = [
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('subject_asc', 'Subject (A-Z)'),
            ('subject_desc', 'Subject (Z-A)'),
            ('status', 'Status'),
            ('sent_desc', 'Sent Date (Newest)'),
            ('sent_asc', 'Sent Date (Oldest)'),
        ]
        return context


class DraftListView(OwnerFilterMixin, ListView):
    model = EmailMessage
    template_name = 'emails/draft_list.html'
    context_object_name = 'emails'
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(is_draft=True, status='draft')
        search = self.request.GET.get('search', '').strip()
        sort = self.request.GET.get('sort', 'newest')
        if search:
            qs = qs.filter(Q(subject__icontains=search) | Q(to_emails__icontains=search))
        ordering = SORT_MAP.get(sort, '-created_at')
        return qs.order_by(ordering)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        context['sort_choices'] = [
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('subject_asc', 'Subject (A-Z)'),
            ('subject_desc', 'Subject (Z-A)'),
        ]
        return context


class EmailDetailView(OwnerFilterMixin, DetailView):
    model = EmailMessage
    template_name = 'emails/email_detail.html'
    context_object_name = 'email'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['attachments'] = self.object.attachments.all()
        return context


class EmailDeleteView(OwnerFilterMixin, DeleteView):
    model = EmailMessage
    template_name = 'emails/email_confirm_delete.html'
    context_object_name = 'email'

    def get_success_url(self):
        email = self.object
        if email.is_draft:
            return reverse_lazy('emails:drafts')
        return reverse_lazy('emails:sent')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(request, 'Email deleted.')
        return response


class EmailCancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        email = get_object_or_404(EmailMessage, pk=pk, owner=request.user)
        if email.status in ('queued', 'scheduled'):
            email.status = 'cancelled'
            email.save(update_fields=['status'])
            messages.success(request, 'Email cancelled.')
        else:
            messages.error(request, 'This email cannot be cancelled.')
        return HttpResponseRedirect(reverse('emails:sent'))


class EmailRetryView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        email = get_object_or_404(EmailMessage, pk=pk, owner=request.user)
        if email.status == 'failed':
            success, error = send_email_message(email)
            if success:
                messages.success(request, 'Email sent successfully.')
            else:
                messages.error(request, f'Retry failed: {error}')
        else:
            messages.error(request, 'Only failed emails can be retried.')
        return HttpResponseRedirect(reverse('emails:sent'))


# ──────────────────────────────────────────────
#  Templates
# ──────────────────────────────────────────────

class TemplateListView(OwnerFilterMixin, ListView):
    model = EmailTemplate
    template_name = 'emails/template_list.html'
    context_object_name = 'templates'
    paginate_by = 15

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.filter(Q(owner=self.request.user) | Q(is_shared=True))
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(subject__icontains=search)
            )
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        return context


class TemplateCreateView(LoginRequiredMixin, CreateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'emails/template_form.html'
    success_url = reverse_lazy('emails:templates')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        messages.success(self.request, 'Template created.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Template'
        return context


class TemplateUpdateView(OwnerFilterMixin, UpdateView):
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'emails/template_form.html'
    success_url = reverse_lazy('emails:templates')

    def form_valid(self, form):
        messages.success(self.request, 'Template updated.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Template'
        return context


class TemplateDeleteView(OwnerFilterMixin, DeleteView):
    model = EmailTemplate
    template_name = 'emails/template_confirm_delete.html'
    context_object_name = 'template'
    success_url = reverse_lazy('emails:templates')

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        messages.success(request, 'Template deleted.')
        return response


# ──────────────────────────────────────────────
#  AJAX endpoints
# ──────────────────────────────────────────────

class TemplateJsonView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        template = get_object_or_404(
            EmailTemplate,
            pk=pk,
        )
        if template.owner != request.user and not template.is_shared:
            return JsonResponse({'error': 'Not found'}, status=404)
        return JsonResponse({
            'id': template.pk,
            'name': template.name,
            'subject': template.subject,
            'body_html': template.body_html,
            'body_plain': template.body_plain,
        })


class EmailStatsJsonView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        qs = EmailMessage.objects.filter(owner=request.user)
        return JsonResponse({
            'total': qs.count(),
            'sent': qs.filter(status='sent').count(),
            'drafts': qs.filter(status='draft', is_draft=True).count(),
            'failed': qs.filter(status='failed').count(),
            'scheduled': qs.filter(status='scheduled').count(),
            'queued': qs.filter(status='queued').count(),
        })
