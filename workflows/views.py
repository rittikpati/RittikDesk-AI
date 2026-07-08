import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View

from core.mixins import OwnerFilterMixin
from .models import (
    Workflow, WorkflowAction, WorkflowExecutionLog, Notification,
)
from .forms import WorkflowForm, WorkflowActionForm


# ---------------------------------------------------------------------------
# Notification views
# ---------------------------------------------------------------------------

class NotificationListView(OwnerFilterMixin, ListView):
    model = Notification
    template_name = 'workflows/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        filter_param = self.request.GET.get('filter', '')
        if filter_param == 'unread':
            qs = qs.filter(is_read=False)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter'] = self.request.GET.get('filter', '')
        context['unread_count'] = Notification.objects.filter(
            owner=self.request.user, is_read=False,
        ).count()
        return context


class NotificationMarkReadView(OwnerFilterMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(
            Notification, pk=self.kwargs['pk'], owner=request.user,
        )
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return JsonResponse({'status': 'ok'})


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(
            owner=request.user, is_read=False,
        ).update(is_read=True)
        return JsonResponse({'status': 'ok'})


class NotificationClearView(OwnerFilterMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(
            Notification, pk=self.kwargs['pk'], owner=request.user,
        )
        notification.delete()
        return JsonResponse({'status': 'ok'})


class NotificationClearAllView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(owner=request.user).delete()
        return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# Workflow CRUD
# ---------------------------------------------------------------------------

class WorkflowListView(OwnerFilterMixin, ListView):
    model = Workflow
    template_name = 'workflows/workflow_list.html'
    context_object_name = 'workflows'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(Q(name__icontains=search))
        trigger = self.request.GET.get('trigger', '')
        if trigger:
            qs = qs.filter(trigger_type=trigger)
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_workflows'] = Workflow.objects.filter(
            owner=self.request.user,
        ).count()
        context['search_query'] = self.request.GET.get('search', '')
        context['active_trigger'] = self.request.GET.get('trigger', '')
        from .models import TRIGGER_CHOICES
        context['trigger_choices'] = TRIGGER_CHOICES
        return context


class WorkflowCreateView(LoginRequiredMixin, CreateView):
    model = Workflow
    form_class = WorkflowForm
    template_name = 'workflows/workflow_form.html'
    success_url = reverse_lazy('workflows:list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Workflow "{form.instance.name}" created successfully.',
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Workflow'
        return context


class WorkflowDetailView(OwnerFilterMixin, DetailView):
    model = Workflow
    template_name = 'workflows/workflow_detail.html'
    context_object_name = 'workflow'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['actions'] = self.object.actions.all().order_by('order')
        context['execution_logs'] = WorkflowExecutionLog.objects.filter(
            workflow=self.object,
        )[:20]
        context['action_choices'] = WorkflowAction._meta.get_field(
            'action_type',
        ).choices
        return context


class WorkflowUpdateView(OwnerFilterMixin, UpdateView):
    model = Workflow
    form_class = WorkflowForm
    template_name = 'workflows/workflow_form.html'
    success_url = reverse_lazy('workflows:list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Workflow "{form.instance.name}" updated successfully.',
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Workflow'
        context['is_update'] = True
        context['actions'] = self.object.actions.all().order_by('order')
        context['action_choices'] = WorkflowAction._meta.get_field(
            'action_type',
        ).choices
        return context


class WorkflowDeleteView(OwnerFilterMixin, DeleteView):
    model = Workflow
    template_name = 'workflows/workflow_confirm_delete.html'
    success_url = reverse_lazy('workflows:list')
    context_object_name = 'workflow'

    def form_valid(self, form):
        messages.success(
            self.request,
            f'Workflow "{self.object.name}" deleted successfully.',
        )
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Workflow Action CRUD (inline via JSON)
# ---------------------------------------------------------------------------

class WorkflowActionCreateView(OwnerFilterMixin, View):
    def post(self, request, workflow_pk):
        workflow = get_object_or_404(
            Workflow, pk=workflow_pk, owner=request.user,
        )
        form = WorkflowActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.workflow = workflow
            action.save()
            return JsonResponse({
                'status': 'ok',
                'action': {
                    'pk': action.pk,
                    'action_type': action.action_type,
                    'order': action.order,
                    'config': action.config,
                },
            })
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class WorkflowActionUpdateView(OwnerFilterMixin, View):
    def post(self, request, workflow_pk, pk):
        action = get_object_or_404(
            WorkflowAction, pk=pk, workflow_id=workflow_pk,
            workflow__owner=request.user,
        )
        form = WorkflowActionForm(request.POST, instance=action)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'ok'})
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


class WorkflowActionDeleteView(OwnerFilterMixin, View):
    def delete(self, request, workflow_pk, pk):
        action = get_object_or_404(
            WorkflowAction, pk=pk, workflow_id=workflow_pk,
            workflow__owner=request.user,
        )
        action.delete()
        return JsonResponse({'status': 'ok'})


# ---------------------------------------------------------------------------
# Workflow toggle
# ---------------------------------------------------------------------------

class WorkflowToggleView(OwnerFilterMixin, View):
    def post(self, request, pk):
        workflow = get_object_or_404(Workflow, pk=pk, owner=request.user)
        workflow.is_active = not workflow.is_active
        workflow.save(update_fields=['is_active'])
        return JsonResponse({
            'status': 'ok',
            'is_active': workflow.is_active,
        })


# ---------------------------------------------------------------------------
# Execution log detail
# ---------------------------------------------------------------------------

class WorkflowExecutionLogDetailView(OwnerFilterMixin, DetailView):
    model = WorkflowExecutionLog
    template_name = 'workflows/execution_log_detail.html'
    context_object_name = 'log'
