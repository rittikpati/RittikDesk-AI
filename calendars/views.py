import calendar as cal_module
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.utils import timezone
from core.mixins import OwnerFilterMixin
from calendars.models import Event
from calendars.forms import EventForm


def apply_filters(qs, search, event_type, status):
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(description__icontains=search))
    if event_type:
        qs = qs.filter(event_type=event_type)
    if status:
        qs = qs.filter(status=status)
    return qs


class EventListView(OwnerFilterMixin, ListView):
    model = Event
    template_name = 'calendar/event_list.html'
    context_object_name = 'events'
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.GET.get('search', '').strip()
        event_type = self.request.GET.get('event_type', '').strip()
        status = self.request.GET.get('status', '').strip()
        view = self.request.GET.get('view', 'list')
        qs = apply_filters(qs, search, event_type, status)
        today = timezone.now().date()
        if view == 'upcoming':
            qs = qs.filter(start_date__gte=today, status='scheduled')
        elif view == 'today':
            qs = qs.filter(start_date=today)
        elif view == 'month':
            pass
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['active_event_type'] = self.request.GET.get('event_type', '')
        context['active_status'] = self.request.GET.get('status', '')
        context['active_view'] = self.request.GET.get('view', 'list')
        context['event_type_choices'] = Event.EVENT_TYPE_CHOICES
        context['status_choices'] = Event.STATUS_CHOICES
        context['today'] = timezone.now().date()

        now = timezone.now()
        year = int(self.request.GET.get('year', now.year))
        month = int(self.request.GET.get('month', now.month))
        month_start = datetime(year, month, 1).date()
        if month == 12:
            month_end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            month_end = datetime(year, month + 1, 1).date() - timedelta(days=1)
        context['month_year'] = month_start.strftime('%B %Y')
        context['month'] = month
        context['year'] = year
        context['prev_month'] = month - 1 if month > 1 else 12
        context['prev_year'] = year if month > 1 else year - 1
        context['next_month'] = month + 1 if month < 12 else 1
        context['next_year'] = year if month < 12 else year + 1

        cal = cal_module.monthcalendar(year, month)
        month_events = Event.objects.filter(
            owner=self.request.user,
            start_date__gte=month_start,
            start_date__lte=month_end,
        ).select_related('owner', 'contact', 'lead', 'task')
        events_by_date = {}
        for e in month_events:
            events_by_date.setdefault(e.start_date, []).append(e)
        context['calendar_days'] = cal
        context['events_by_date'] = events_by_date
        context['month_start'] = month_start

        return context


class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar/event_form.html'
    success_url = reverse_lazy('calendars:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, f'Event "{form.instance.title}" created successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Event'
        return context


class EventDetailView(OwnerFilterMixin, DetailView):
    model = Event
    template_name = 'calendar/event_detail.html'
    context_object_name = 'event'


class EventUpdateView(OwnerFilterMixin, UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'calendar/event_form.html'
    success_url = reverse_lazy('calendars:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Event "{form.instance.title}" updated successfully.')
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Event'
        context['is_update'] = True
        return context


class EventDeleteView(OwnerFilterMixin, DeleteView):
    model = Event
    template_name = 'calendar/event_confirm_delete.html'
    success_url = reverse_lazy('calendars:list')
    context_object_name = 'event'

    def form_valid(self, form):
        messages.success(self.request, f'Event "{self.object.title}" deleted successfully.')
        return super().form_valid(form)
