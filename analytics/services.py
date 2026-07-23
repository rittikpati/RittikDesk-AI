from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum, Count, Q, F
from django.utils import timezone


class PipelineAnalyticsService:
    """Compute all pipeline analytics from live Deal data for a single user.

    Every method filters by ``owner=user`` and returns plain dicts/numbers
    safe for template rendering.  Never fabricates values.
    """

    STAGE_ORDER = [
        'New', 'Qualified', 'Proposal Sent', 'Negotiation',
        'Contract Review', 'Won', 'Lost',
    ]

    STAGE_COLORS = {
        'New': '#00B4D8',
        'Qualified': '#6C63FF',
        'Proposal Sent': '#FFB800',
        'Negotiation': '#E040FB',
        'Contract Review': '#FF8A65',
        'Won': '#00D9A6',
        'Lost': '#FF6B6B',
    }

    def __init__(self, user):
        self.user = user
        self.today = date.today()
        self._qs = None

    @property
    def deals(self):
        if self._qs is None:
            self._qs = self.user.deals.all()
        return self._qs

    # ------------------------------------------------------------------
    # KPI summary cards
    # ------------------------------------------------------------------
    def get_kpi_summary(self):
        qs = self.deals
        total = qs.count()
        won = qs.filter(stage='Won')
        lost = qs.filter(stage='Lost')
        open_deals = qs.exclude(stage__in=['Won', 'Lost'])

        won_count = won.count()
        lost_count = lost.count()
        closed_count = won_count + lost_count
        win_rate = (won_count / closed_count * 100) if closed_count else 0

        won_value = won.aggregate(v=Sum('value'))['v'] or Decimal('0')
        pipeline_value = open_deals.aggregate(v=Sum('value'))['v'] or Decimal('0')
        avg_value = (qs.aggregate(v=Sum('value'))['v'] or Decimal('0')) / total if total else Decimal('0')

        return {
            'total_deals': total,
            'open_deals_count': open_deals.count(),
            'won_deals_count': won_count,
            'lost_deals_count': lost_count,
            'pipeline_value': pipeline_value,
            'won_revenue': won_value,
            'avg_deal_value': avg_value,
            'win_rate': round(win_rate, 1),
        }

    # ------------------------------------------------------------------
    # Pipeline stage breakdown
    # ------------------------------------------------------------------
    def get_stage_breakdown(self):
        qs = self.deals
        stages = []
        for stage_name in self.STAGE_ORDER:
            stage_qs = qs.filter(stage=stage_name)
            count = stage_qs.count()
            value = stage_qs.aggregate(v=Sum('value'))['v'] or Decimal('0')
            stages.append({
                'stage': stage_name,
                'count': count,
                'value': value,
                'color': self.STAGE_COLORS.get(stage_name, '#6C63FF'),
            })
        return stages

    # ------------------------------------------------------------------
    # Revenue forecast
    # ------------------------------------------------------------------
    def get_revenue_forecast(self):
        today = self.today
        month_start = today.replace(day=1)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1, day=1)

        if next_month_start.month == 12:
            next_month_end = next_month_start.replace(year=next_month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            next_month_end = next_month_start.replace(month=next_month_start.month + 1, day=1) - timedelta(days=1)

        open_deals = self.deals.exclude(stage__in=['Won', 'Lost'])

        this_month_deals = open_deals.filter(
            expected_close_date__gte=month_start,
            expected_close_date__lte=today.replace(day=31) if today.month == 12 else (month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)),
        )
        next_month_deals = open_deals.filter(
            expected_close_date__gte=next_month_start,
            expected_close_date__lte=next_month_end,
        )

        this_month_est = sum(
            (d.value or Decimal('0')) * (d.probability or 0) / 100
            for d in this_month_deals
        )
        next_month_est = sum(
            (d.value or Decimal('0')) * (d.probability or 0) / 100
            for d in next_month_deals
        )
        projected_pipeline = sum(
            (d.value or Decimal('0')) * (d.probability or 0) / 100
            for d in open_deals
        )

        return {
            'estimated_this_month': Decimal(str(round(this_month_est, 2))),
            'estimated_next_month': Decimal(str(round(next_month_est, 2))),
            'projected_pipeline': Decimal(str(round(projected_pipeline, 2))),
        }

    # ------------------------------------------------------------------
    # Top active opportunities (largest open deals)
    # ------------------------------------------------------------------
    def get_top_opportunities(self, limit=5):
        return list(
            self.deals
            .exclude(stage__in=['Won', 'Lost'])
            .order_by('-value')[:limit]
        )

    # ------------------------------------------------------------------
    # Recent won deals
    # ------------------------------------------------------------------
    def get_recent_won(self, limit=5):
        return list(
            self.deals
            .filter(stage='Won')
            .order_by('-updated_at')[:limit]
        )

    # ------------------------------------------------------------------
    # Monthly revenue trend (last 6 months)
    # ------------------------------------------------------------------
    def get_monthly_trend(self):
        today = self.today
        months = []
        for i in range(5, -1, -1):
            d = today - timedelta(days=30 * i)
            month_start = d.replace(day=1)
            if d.month == 12:
                month_end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
            won_val = (
                self.deals
                .filter(stage='Won', updated_at__date__gte=month_start, updated_at__date__lte=month_end)
                .aggregate(v=Sum('value'))['v'] or Decimal('0')
            )
            months.append({
                'month': month_start.strftime('%b %Y'),
                'won_revenue': won_val,
            })
        return months

    # ------------------------------------------------------------------
    # Source breakdown for open deals
    # ------------------------------------------------------------------
    def get_source_breakdown(self):
        return list(
            self.deals
            .exclude(stage__in=['Won', 'Lost'])
            .values('source')
            .annotate(count=Count('id'), total_value=Sum('value'))
            .order_by('-count')
        )

    # ------------------------------------------------------------------
    # Priority distribution
    # ------------------------------------------------------------------
    def get_priority_breakdown(self):
        return list(
            self.deals
            .exclude(stage__in=['Won', 'Lost'])
            .values('priority')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
