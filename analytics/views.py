from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .services import PipelineAnalyticsService


class PipelineAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/pipeline_analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        svc = PipelineAnalyticsService(self.request.user)

        ctx['kpi'] = svc.get_kpi_summary()
        ctx['stages'] = svc.get_stage_breakdown()
        ctx['forecast'] = svc.get_revenue_forecast()
        ctx['top_opportunities'] = svc.get_top_opportunities()
        ctx['recent_won'] = svc.get_recent_won()
        ctx['monthly_trend'] = svc.get_monthly_trend()
        ctx['source_breakdown'] = svc.get_source_breakdown()
        ctx['priority_breakdown'] = svc.get_priority_breakdown()
        ctx['page_title'] = 'Sales Pipeline Analytics'
        return ctx
