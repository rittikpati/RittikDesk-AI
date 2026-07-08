from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from core.mixins import OwnerFilterMixin
from .models import Task
from .forms import TaskForm


SORT_MAP = {
    'newest': '-created_at',
    'oldest': 'created_at',
    'due_date_asc': 'due_date',
    'due_date_desc': '-due_date',
    'priority': 'priority',
    'status': 'status',
}

STATUS_CHOICES = ['pending', 'in_progress', 'completed']
PRIORITY_CHOICES = ['low', 'medium', 'high']
DATE_FILTERS = ['overdue', 'today', 'this_week', 'this_month']


def apply_filters(qs, search, status, priority, due_date, sort):
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if status in STATUS_CHOICES:
        qs = qs.filter(status=status)
    if priority in PRIORITY_CHOICES:
        qs = qs.filter(priority=priority)
    today = timezone.now().date()
    if due_date == 'overdue':
        qs = qs.filter(due_date__lt=today, status='pending')
    elif due_date == 'today':
        qs = qs.filter(due_date=today)
    elif due_date == 'this_week':
        end = today + timedelta(days=6 - today.weekday())
        qs = qs.filter(due_date__range=[today, end])
    elif due_date == 'this_month':
        qs = qs.filter(due_date__year=today.year, due_date__month=today.month)
    ordering = SORT_MAP.get(sort, '-created_at')
    qs = qs.order_by(ordering)
    return qs


class TaskListView(OwnerFilterMixin, ListView):
    model = Task
    template_name = 'tasks/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        status = self.request.GET.get('status', '').strip()
        priority = self.request.GET.get('priority', '').strip()
        due_date = self.request.GET.get('due_date', '').strip()
        sort = self.request.GET.get('sort', 'newest')
        return apply_filters(qs, search, status, priority, due_date, sort)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['active_priority'] = self.request.GET.get('priority', '')
        context['active_due_date'] = self.request.GET.get('due_date', '')
        context['sort_by'] = self.request.GET.get('sort', 'newest')
        context['status_choices'] = [
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ]
        context['priority_choices'] = [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
        ]
        context['date_filter_choices'] = [
            ('overdue', 'Overdue'),
            ('today', 'Due Today'),
            ('this_week', 'Due This Week'),
            ('this_month', 'Due This Month'),
        ]
        context['sort_choices'] = [
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('due_date_asc', 'Due Date (Earliest)'),
            ('due_date_desc', 'Due Date (Latest)'),
            ('priority', 'Priority'),
            ('status', 'Status'),
        ]
        return context


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    success_url = reverse_lazy('tasks:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Task "{form.instance.title}" created successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Task'
        return context


class TaskDetailView(OwnerFilterMixin, DetailView):
    model = Task
    template_name = 'tasks/task_detail.html'
    context_object_name = 'task'


class TaskUpdateView(OwnerFilterMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task_form.html'
    success_url = reverse_lazy('tasks:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Task "{form.instance.title}" updated successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Task'
        context['is_update'] = True
        return context


class TaskDeleteView(OwnerFilterMixin, DeleteView):
    model = Task
    template_name = 'tasks/task_confirm_delete.html'
    success_url = reverse_lazy('tasks:list')
    context_object_name = 'task'

    def form_valid(self, form):
        messages.success(self.request, f'Task "{self.object.title}" deleted successfully.')
        return super().form_valid(form)
