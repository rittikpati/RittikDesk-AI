from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .models import ActivityLog


MODULE_CHOICES = ActivityLog.MODULE_CHOICES
MODULE_MAP = {key: label for key, label in MODULE_CHOICES}


class ActivityTimelineView(LoginRequiredMixin, TemplateView):
    template_name = 'activities/timeline.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['module_choices'] = MODULE_CHOICES
        return context


class ActivityJSONView(LoginRequiredMixin, TemplateView):
    """Return paginated, filtered activities as JSON."""

    def get(self, request):
        user = request.user
        qs = ActivityLog.objects.filter(user=user).select_related('user')

        # ── Filters ──
        module = request.GET.get('module', '').strip()
        if module and module in MODULE_MAP:
            qs = qs.filter(module=module)

        activity_type = request.GET.get('type', '').strip()
        if activity_type:
            qs = qs.filter(activity_type=activity_type)

        time_filter = request.GET.get('time', '').strip()
        now = timezone.now()
        if time_filter == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            qs = qs.filter(timestamp__gte=start)
        elif time_filter == 'week':
            start = now - timedelta(days=7)
            qs = qs.filter(timestamp__gte=start)
        elif time_filter == 'month':
            start = now - timedelta(days=30)
            qs = qs.filter(timestamp__gte=start)

        # ── Search ──
        search = request.GET.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(object_repr__icontains=search)
            )

        # ── Pagination ──
        page = max(1, int(request.GET.get('page', 1)))
        per_page = min(50, max(1, int(request.GET.get('per_page', 20))))
        total = qs.count()
        offset = (page - 1) * per_page
        activities = qs[offset:offset + per_page]

        results = []
        for a in activities:
            results.append({
                'id': a.pk,
                'activity_type': a.activity_type,
                'title': a.title,
                'description': a.description,
                'module': a.module,
                'module_label': MODULE_MAP.get(a.module, a.module),
                'icon': a.icon,
                'color': a.color,
                'object_id': a.object_id,
                'object_repr': a.object_repr,
                'detail_url': a.detail_url,
                'timestamp': a.timestamp.isoformat(),
                'time_ago': _time_ago(a.timestamp, now),
            })

        return JsonResponse({
            'activities': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'has_next': offset + per_page < total,
        })


def _time_ago(dt, now):
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return 'just now'
    elif seconds < 3600:
        mins = seconds // 60
        return f'{mins} minute{"s" if mins != 1 else ""} ago'
    elif seconds < 86400:
        hours = seconds // 3600
        return f'{hours} hour{"s" if hours != 1 else ""} ago'
    else:
        days = seconds // 86400
        if days < 7:
            return f'{days} day{"s" if days != 1 else ""} ago'
        elif days < 30:
            weeks = days // 7
            return f'{weeks} week{"s" if weeks != 1 else ""} ago'
        else:
            months = days // 30
            return f'{months} month{"s" if months != 1 else ""} ago'
