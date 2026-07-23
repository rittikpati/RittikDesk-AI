from decimal import Decimal
from datetime import date, timedelta

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from deals.models import Deal
from analytics.services import PipelineAnalyticsService


User = get_user_model()


class PipelineAnalyticsServiceTest(TestCase):
    """Test analytics calculations with real Deal data."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='analytics@test.com', username='anatest', password='pass1234',
        )
        cls.other_user = User.objects.create_user(
            email='other@test.com', username='otheruser', password='pass1234',
        )

        today = date.today()
        month_start = today.replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)

        # User deals
        cls.deal_open1 = Deal.objects.create(
            owner=cls.user, deal_name='Open Deal A', value=Decimal('10000'),
            stage='New', probability=20, expected_close_date=today + timedelta(days=15),
        )
        cls.deal_open2 = Deal.objects.create(
            owner=cls.user, deal_name='Open Deal B', value=Decimal('25000'),
            stage='Qualified', probability=50, expected_close_date=today + timedelta(days=20),
        )
        cls.deal_negotiation = Deal.objects.create(
            owner=cls.user, deal_name='Negotiation Deal', value=Decimal('50000'),
            stage='Negotiation', probability=70, expected_close_date=next_month + timedelta(days=10),
        )
        cls.deal_won = Deal.objects.create(
            owner=cls.user, deal_name='Won Deal', value=Decimal('30000'),
            stage='Won', probability=100,
        )
        cls.deal_lost = Deal.objects.create(
            owner=cls.user, deal_name='Lost Deal', value=Decimal('15000'),
            stage='Lost', probability=0,
        )
        cls.deal_proposal = Deal.objects.create(
            owner=cls.user, deal_name='Proposal Deal', value=Decimal('20000'),
            stage='Proposal Sent', probability=40, expected_close_date=next_month + timedelta(days=5),
        )
        cls.deal_contract = Deal.objects.create(
            owner=cls.user, deal_name='Contract Review', value=Decimal('35000'),
            stage='Contract Review', probability=80, expected_close_date=today + timedelta(days=10),
        )

        # Other user's deal (should never appear)
        Deal.objects.create(
            owner=cls.other_user, deal_name='Other User Deal', value=Decimal('99999'),
            stage='New', probability=10,
        )

    def setUp(self):
        self.svc = PipelineAnalyticsService(self.user)

    # ── KPI Summary ──

    def test_total_deals_count(self):
        kpi = self.svc.get_kpi_summary()
        self.assertEqual(kpi['total_deals'], 7)

    def test_open_deals_count(self):
        kpi = self.svc.get_kpi_summary()
        self.assertEqual(kpi['open_deals_count'], 5)

    def test_won_deals_count(self):
        kpi = self.svc.get_kpi_summary()
        self.assertEqual(kpi['won_deals_count'], 1)

    def test_lost_deals_count(self):
        kpi = self.svc.get_kpi_summary()
        self.assertEqual(kpi['lost_deals_count'], 1)

    def test_pipeline_value(self):
        kpi = self.svc.get_kpi_summary()
        # Open: 10000 + 25000 + 50000 + 20000 + 35000 = 140000
        self.assertEqual(kpi['pipeline_value'], Decimal('140000'))

    def test_won_revenue(self):
        kpi = self.svc.get_kpi_summary()
        self.assertEqual(kpi['won_revenue'], Decimal('30000'))

    def test_avg_deal_value(self):
        kpi = self.svc.get_kpi_summary()
        # (10000+25000+50000+30000+15000+20000+35000)/7 = 185000/7
        expected = Decimal('185000') / 7
        self.assertEqual(kpi['avg_deal_value'].quantize(Decimal('0.01')), expected.quantize(Decimal('0.01')))

    def test_win_rate(self):
        kpi = self.svc.get_kpi_summary()
        # 1 won / (1 won + 1 lost) = 50%
        self.assertEqual(kpi['win_rate'], 50.0)

    def test_win_rate_no_closed_deals(self):
        svc = PipelineAnalyticsService(self.other_user)
        kpi = svc.get_kpi_summary()
        self.assertEqual(kpi['win_rate'], 0)

    # ── Stage Breakdown ──

    def test_stage_breakdown_returns_all_stages(self):
        stages = self.svc.get_stage_breakdown()
        self.assertEqual(len(stages), 7)
        stage_names = [s['stage'] for s in stages]
        self.assertEqual(stage_names, [
            'New', 'Qualified', 'Proposal Sent', 'Negotiation',
            'Contract Review', 'Won', 'Lost',
        ])

    def test_stage_breakdown_correct_counts(self):
        stages = self.svc.get_stage_breakdown()
        counts = {s['stage']: s['count'] for s in stages}
        self.assertEqual(counts['New'], 1)
        self.assertEqual(counts['Qualified'], 1)
        self.assertEqual(counts['Proposal Sent'], 1)
        self.assertEqual(counts['Negotiation'], 1)
        self.assertEqual(counts['Contract Review'], 1)
        self.assertEqual(counts['Won'], 1)
        self.assertEqual(counts['Lost'], 1)

    # ── Revenue Forecast ──

    def test_forecast_returns_keys(self):
        forecast = self.svc.get_revenue_forecast()
        self.assertIn('estimated_this_month', forecast)
        self.assertIn('estimated_next_month', forecast)
        self.assertIn('projected_pipeline', forecast)

    def test_forecast_projected_pipeline(self):
        forecast = self.svc.get_revenue_forecast()
        # Expected weighted: 10000*0.2 + 25000*0.5 + 50000*0.7 + 20000*0.4 + 35000*0.8
        # = 2000 + 12500 + 35000 + 8000 + 28000 = 85500
        self.assertEqual(forecast['projected_pipeline'], Decimal('85500.00'))

    # ── Top Opportunities ──

    def test_top_opportunities_excludes_won_lost(self):
        top = self.svc.get_top_opportunities()
        names = [d.deal_name for d in top]
        self.assertNotIn('Won Deal', names)
        self.assertNotIn('Lost Deal', names)

    def test_top_opportunities_ordered_by_value(self):
        top = self.svc.get_top_opportunities()
        values = [d.value for d in top]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_top_opportunities_limit(self):
        top = self.svc.get_top_opportunities(limit=3)
        self.assertEqual(len(top), 3)

    # ── Recent Won ──

    def test_recent_won_only_won(self):
        won = self.svc.get_recent_won()
        for d in won:
            self.assertEqual(d.stage, 'Won')

    def test_recent_won_limit(self):
        won = self.svc.get_recent_won(limit=1)
        self.assertEqual(len(won), 1)

    # ── Monthly Trend ──

    def test_monthly_trend_returns_6_months(self):
        trend = self.svc.get_monthly_trend()
        self.assertEqual(len(trend), 6)
        for item in trend:
            self.assertIn('month', item)
            self.assertIn('won_revenue', item)

    # ── Source Breakdown ──

    def test_source_breakdown(self):
        sources = self.svc.get_source_breakdown()
        self.assertIsInstance(sources, list)
        # All our test deals default to 'Website'
        if sources:
            self.assertEqual(sources[0]['source'], 'Website')

    # ── Priority Breakdown ──

    def test_priority_breakdown(self):
        priorities = self.svc.get_priority_breakdown()
        self.assertIsInstance(priorities, list)

    # ── Owner isolation ──

    def test_other_user_sees_nothing(self):
        svc = PipelineAnalyticsService(self.other_user)
        kpi = svc.get_kpi_summary()
        self.assertEqual(kpi['total_deals'], 1)
        self.assertEqual(kpi['pipeline_value'], Decimal('99999'))


class PipelineAnalyticsViewTest(TestCase):
    """Test the analytics view requires login and returns correct data."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='viewtest@test.com', username='viewtester', password='pass1234',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(email='viewtest@test.com', password='pass1234')

    def test_view_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertEqual(resp.status_code, 302)

    def test_view_returns_200(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertEqual(resp.status_code, 200)

    def test_view_uses_correct_template(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertTemplateUsed(resp, 'analytics/pipeline_analytics.html')

    def test_view_context_has_kpi(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('kpi', resp.context)

    def test_view_context_has_stages(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('stages', resp.context)

    def test_view_context_has_forecast(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('forecast', resp.context)

    def test_view_context_has_top_opportunities(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('top_opportunities', resp.context)

    def test_view_context_has_recent_won(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('recent_won', resp.context)

    def test_view_context_has_monthly_trend(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertIn('monthly_trend', resp.context)

    def test_view_empty_deals(self):
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertEqual(resp.context['kpi']['total_deals'], 0)

    def test_view_with_deals(self):
        Deal.objects.create(
            owner=self.user, deal_name='Test Deal', value=Decimal('5000'),
            stage='New', probability=25,
        )
        resp = self.client.get(reverse('analytics:pipeline'))
        self.assertEqual(resp.context['kpi']['total_deals'], 1)


class AnalyticsAIAgentTest(TestCase):
    """Test the AnalyticsAction pipeline query methods."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email='aitest@test.com', username='aitester', password='pass1234',
        )
        Deal.objects.create(
            owner=cls.user, deal_name='AI Test Deal', value=Decimal('10000'),
            stage='New', probability=30,
        )
        Deal.objects.create(
            owner=cls.user, deal_name='AI Won Deal', value=Decimal('20000'),
            stage='Won', probability=100,
        )

    def setUp(self):
        from assistant.action_layer import AnalyticsAction
        self.action = AnalyticsAction()

    def test_pipeline_summary_contains_deals(self):
        result = self.action.execute('show pipeline summary', self.user)
        self.assertIn('Total Deals', result)
        self.assertIn('2', result)

    def test_pipeline_stages(self):
        result = self.action.execute('show pipeline stages', self.user)
        self.assertIn('New', result)
        self.assertIn('Won', result)

    def test_revenue_forecast(self):
        result = self.action.execute('revenue forecast', self.user)
        self.assertIn('Revenue Forecast', result)
        self.assertIn('Estimated This Month', result)

    def test_top_deals(self):
        result = self.action.execute('show top deals', self.user)
        self.assertIn('Top Active Opportunities', result)
        self.assertIn('AI Test Deal', result)
        self.assertNotIn('AI Won Deal', result)

    def test_won_deals(self):
        result = self.action.execute('show won deals', self.user)
        self.assertIn('Recent Won Deals', result)
        self.assertIn('AI Won Deal', result)

    def test_lost_deals_empty(self):
        result = self.action.execute('show lost deals', self.user)
        self.assertIn('No lost deals', result)

    def test_deal_analytics(self):
        result = self.action.execute('deal analytics', self.user)
        self.assertIn('Sales Pipeline Summary', result)
