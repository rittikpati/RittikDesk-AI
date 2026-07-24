import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import ActivityLog
from .services import log_activity, ACTIVITY_TYPES
from .views import _time_ago

User = get_user_model()


class ActivityLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='model@example.com', username='modeluser', password='pass1234',
        )

    def test_create_activity_log(self):
        log = ActivityLog.objects.create(
            user=self.user, activity_type='contact_created', title='Test',
            module='contacts', icon='fa-user', color='#000',
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.activity_type, 'contact_created')
        self.assertEqual(log.module, 'contacts')
        self.assertIsNotNone(log.timestamp)

    def test_str(self):
        log = ActivityLog.objects.create(
            user=self.user, activity_type='test_type', title='Hello',
        )
        s = str(log)
        self.assertIn('test_type', s)
        self.assertIn('model@example.com', s)

    def test_defaults(self):
        log = ActivityLog.objects.create(
            user=self.user, activity_type='test', title='X',
        )
        self.assertEqual(log.module, 'system')
        self.assertEqual(log.icon, 'fa-info-circle')
        self.assertEqual(log.color, '#6C63FF')
        self.assertEqual(log.description, '')
        self.assertIsNone(log.object_id)
        self.assertEqual(log.object_repr, '')
        self.assertEqual(log.detail_url, '')

    def test_ordering(self):
        ActivityLog.objects.create(user=self.user, activity_type='first', title='A')
        ActivityLog.objects.create(user=self.user, activity_type='second', title='B')
        qs = list(ActivityLog.objects.values_list('activity_type', flat=True))
        self.assertEqual(qs, ['second', 'first'])

    def test_cascade_delete_user(self):
        ActivityLog.objects.create(user=self.user, activity_type='test', title='X')
        self.user.delete()
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_nullable_object_id(self):
        log = ActivityLog.objects.create(
            user=self.user, activity_type='test', title='X', object_id=None,
        )
        self.assertIsNone(log.object_id)

    def test_module_choices_valid(self):
        for key, _ in ActivityLog.MODULE_CHOICES:
            log = ActivityLog.objects.create(
                user=self.user, activity_type='test', title='X', module=key,
            )
            self.assertEqual(log.module, key)


class LogActivityServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='svc@example.com', username='svcuser', password='pass1234',
        )

    def test_predefined_type_auto_fills(self):
        log_activity(self.user, 'contact_created', name='John')
        log = ActivityLog.objects.get()
        self.assertEqual(log.module, 'contacts')
        self.assertEqual(log.icon, 'fa-user-plus')
        self.assertEqual(log.color, '#6C63FF')
        self.assertEqual(log.title, 'Contact "John" created')
        self.assertEqual(log.activity_type, 'contact_created')

    def test_title_template_with_extra_kwargs(self):
        log_activity(self.user, 'deal_stage_changed', name='Big Deal', stage='Won')
        log = ActivityLog.objects.get()
        self.assertEqual(log.title, 'Deal "Big Deal" moved to Won')

    def test_custom_title_overrides_template(self):
        log_activity(self.user, 'contact_created', title='Custom title', name='Ignored')
        log = ActivityLog.objects.get()
        self.assertEqual(log.title, 'Custom title')

    def test_explicit_module_icon_color_override(self):
        log_activity(self.user, 'contact_created', name='X',
                     module='custom', icon='fa-star', color='#FFF')
        log = ActivityLog.objects.get()
        self.assertEqual(log.module, 'custom')
        self.assertEqual(log.icon, 'fa-star')
        self.assertEqual(log.color, '#FFF')

    def test_unknown_activity_type_defaults(self):
        log_activity(self.user, 'something_weird', title='Hello')
        log = ActivityLog.objects.get()
        self.assertEqual(log.activity_type, 'something_weird')
        self.assertEqual(log.module, 'system')
        self.assertEqual(log.icon, 'fa-info-circle')

    def test_none_activity_type(self):
        log_activity(self.user, activity_type=None, title='No type')
        log = ActivityLog.objects.get()
        self.assertEqual(log.activity_type, 'unknown')
        self.assertEqual(log.title, 'No type')

    def test_description_saved(self):
        log_activity(self.user, 'contact_created', name='X', description='Desc text')
        log = ActivityLog.objects.get()
        self.assertEqual(log.description, 'Desc text')

    def test_object_fields_saved(self):
        log_activity(self.user, 'contact_created', name='X',
                     object_id=42, object_repr='John', detail_url='/contacts/42/')
        log = ActivityLog.objects.get()
        self.assertEqual(log.object_id, 42)
        self.assertEqual(log.object_repr, 'John')
        self.assertEqual(log.detail_url, '/contacts/42/')

    def test_object_repr_defaults_to_name(self):
        log_activity(self.user, 'contact_created', name='Jane')
        log = ActivityLog.objects.get()
        self.assertEqual(log.object_repr, 'Jane')

    def test_db_error_swallows(self):
        with patch('activities.models.ActivityLog.save', side_effect=Exception('DB down')):
            log_activity(self.user, 'contact_created', name='X')
        self.assertEqual(ActivityLog.objects.count(), 0)

    def test_all_predefined_types_exist(self):
        expected = [
            'contact_created', 'contact_updated', 'contact_deleted',
            'company_created', 'company_updated', 'company_deleted',
            'lead_created', 'lead_updated', 'lead_converted', 'lead_deleted',
            'deal_created', 'deal_stage_changed', 'deal_won', 'deal_lost',
            'deal_updated', 'deal_deleted',
            'task_created', 'task_completed', 'task_updated', 'task_deleted',
            'campaign_created', 'campaign_updated', 'campaign_deleted',
            'email_sent', 'email_scheduled', 'email_draft',
            'meeting_created', 'meeting_updated', 'meeting_completed', 'meeting_deleted',
            'workflow_executed',
            'ai_created_contact', 'ai_created_task', 'ai_created_deal',
            'ai_created_company', 'ai_created_lead', 'ai_sent_email', 'ai_created_campaign',
            'user_login',
        ]
        for key in expected:
            self.assertIn(key, ACTIVITY_TYPES)
            cfg = ACTIVITY_TYPES[key]
            self.assertIn('module', cfg)
            self.assertIn('icon', cfg)
            self.assertIn('color', cfg)
            self.assertIn('title_tpl', cfg)

    def test_user_logged_in_type(self):
        log_activity(self.user, 'user_login')
        log = ActivityLog.objects.get()
        self.assertEqual(log.module, 'system')
        self.assertEqual(log.title, 'User logged in')

    def test_title_template_no_name(self):
        log_activity(self.user, 'workflow_executed', name='MyFlow')
        log = ActivityLog.objects.get()
        self.assertEqual(log.title, 'Workflow "MyFlow" executed')


class TimeAgoTest(TestCase):
    def test_just_now(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(seconds=30), now), 'just now')

    def test_minutes(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(minutes=5), now), '5 minutes ago')

    def test_minute_singular(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(minutes=1), now), '1 minute ago')

    def test_hours(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(hours=3), now), '3 hours ago')

    def test_hour_singular(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(hours=1), now), '1 hour ago')

    def test_days(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=5), now), '5 days ago')

    def test_day_singular(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=1), now), '1 day ago')

    def test_weeks(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=14), now), '2 weeks ago')

    def test_week_singular(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=7), now), '1 week ago')

    def test_months(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=60), now), '2 months ago')

    def test_month_singular(self):
        now = timezone.now()
        self.assertEqual(_time_ago(now - timedelta(days=30), now), '1 month ago')


class ActivityTimelineViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='view@example.com', username='viewuser', password='pass1234',
        )

    def test_redirect_if_not_logged_in(self):
        resp = self.client.get(reverse('activities:timeline'))
        self.assertEqual(resp.status_code, 302)

    def test_renders_if_logged_in(self):
        self.client.login(email='view@example.com', password='pass1234')
        resp = self.client.get(reverse('activities:timeline'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('module_choices', resp.context)


class ActivityJSONViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='json@example.com', username='jsonuser', password='pass1234',
        )
        self.other = User.objects.create_user(
            email='other@example.com', username='otheruser', password='pass1234',
        )
        self.client.login(email='json@example.com', password='pass1234')
        self.url = reverse('activities:json')

    def _create_logs(self, user, count=3, **overrides):
        for i in range(count):
            ActivityLog.objects.create(
                user=user, activity_type='test', title=f'Log {i}', **overrides,
            )

    def test_redirect_if_not_logged_in(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)

    def test_returns_json(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('activities', data)
        self.assertIn('total', data)
        self.assertIn('has_next', data)

    def test_empty_results(self):
        resp = self.client.get(self.url)
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 0)
        self.assertEqual(data['activities'], [])

    def test_shows_own_activities(self):
        self._create_logs(self.user, 2)
        self._create_logs(self.other, 5)
        resp = self.client.get(self.url)
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 2)

    def test_filter_by_module(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='a', title='Contacts', module='contacts',
        )
        ActivityLog.objects.create(
            user=self.user, activity_type='b', title='Deals', module='deals',
        )
        resp = self.client.get(self.url, {'module': 'contacts'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['activities'][0]['module'], 'contacts')

    def test_filter_invalid_module_ignored(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='a', title='X', module='contacts',
        )
        resp = self.client.get(self.url, {'module': 'bogus'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_filter_by_activity_type(self):
        ActivityLog.objects.create(user=self.user, activity_type='type_a', title='A')
        ActivityLog.objects.create(user=self.user, activity_type='type_b', title='B')
        resp = self.client.get(self.url, {'type': 'type_a'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['activities'][0]['activity_type'], 'type_a')

    def test_filter_by_time_today(self):
        ActivityLog.objects.create(user=self.user, activity_type='t', title='Old')
        ActivityLog.objects.filter(user=self.user).update(
            timestamp=timezone.now() - timedelta(days=3),
        )
        ActivityLog.objects.create(user=self.user, activity_type='t', title='New')
        resp = self.client.get(self.url, {'time': 'today'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['activities'][0]['title'], 'New')

    def test_filter_by_time_week(self):
        ActivityLog.objects.create(user=self.user, activity_type='t', title='Old')
        ActivityLog.objects.filter(user=self.user).update(
            timestamp=timezone.now() - timedelta(days=10),
        )
        ActivityLog.objects.create(user=self.user, activity_type='t', title='New')
        resp = self.client.get(self.url, {'time': 'week'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_filter_by_time_month(self):
        ActivityLog.objects.create(user=self.user, activity_type='t', title='Old')
        ActivityLog.objects.filter(user=self.user).update(
            timestamp=timezone.now() - timedelta(days=35),
        )
        ActivityLog.objects.create(user=self.user, activity_type='t', title='New')
        resp = self.client.get(self.url, {'time': 'month'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_search_by_title(self):
        ActivityLog.objects.create(user=self.user, activity_type='t', title='Hello World')
        ActivityLog.objects.create(user=self.user, activity_type='t', title='Goodbye')
        resp = self.client.get(self.url, {'q': 'hello'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)
        self.assertEqual(data['activities'][0]['title'], 'Hello World')

    def test_search_by_description(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='t', title='X', description='important note',
        )
        resp = self.client.get(self.url, {'q': 'important'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_search_by_object_repr(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='t', title='X', object_repr='Acme Corp',
        )
        resp = self.client.get(self.url, {'q': 'acme'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_pagination(self):
        for i in range(25):
            ActivityLog.objects.create(user=self.user, activity_type='t', title=f'Log {i}')
        resp = self.client.get(self.url, {'per_page': 10, 'page': 1})
        data = json.loads(resp.content)
        self.assertEqual(len(data['activities']), 10)
        self.assertEqual(data['total'], 25)
        self.assertTrue(data['has_next'])

    def test_pagination_page_2(self):
        for i in range(25):
            ActivityLog.objects.create(user=self.user, activity_type='t', title=f'Log {i}')
        resp = self.client.get(self.url, {'per_page': 10, 'page': 3})
        data = json.loads(resp.content)
        self.assertEqual(len(data['activities']), 5)
        self.assertFalse(data['has_next'])

    def test_per_page_max_50(self):
        for i in range(60):
            ActivityLog.objects.create(user=self.user, activity_type='t', title=f'Log {i}')
        resp = self.client.get(self.url, {'per_page': 100})
        data = json.loads(resp.content)
        self.assertEqual(len(data['activities']), 50)

    def test_per_page_min_1(self):
        resp = self.client.get(self.url, {'per_page': -5})
        data = json.loads(resp.content)
        self.assertEqual(data['per_page'], 1)

    def test_page_min_1(self):
        resp = self.client.get(self.url, {'page': -3})
        data = json.loads(resp.content)
        self.assertEqual(data['page'], 1)

    def test_activity_fields_in_response(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='contact_created', title='Test',
            description='Desc', module='contacts', icon='fa-user',
            color='#000', object_id=1, object_repr='John',
            detail_url='/contacts/1/',
        )
        resp = self.client.get(self.url)
        data = json.loads(resp.content)
        a = data['activities'][0]
        self.assertEqual(a['activity_type'], 'contact_created')
        self.assertEqual(a['title'], 'Test')
        self.assertEqual(a['description'], 'Desc')
        self.assertEqual(a['module'], 'contacts')
        self.assertEqual(a['module_label'], 'Contacts')
        self.assertEqual(a['icon'], 'fa-user')
        self.assertEqual(a['color'], '#000')
        self.assertEqual(a['object_id'], 1)
        self.assertEqual(a['object_repr'], 'John')
        self.assertEqual(a['detail_url'], '/contacts/1/')
        self.assertIn('timestamp', a)
        self.assertIn('time_ago', a)

    def test_combined_filters(self):
        ActivityLog.objects.create(
            user=self.user, activity_type='a', title='Contacts', module='contacts',
        )
        ActivityLog.objects.create(
            user=self.user, activity_type='b', title='Deals', module='deals',
        )
        resp = self.client.get(self.url, {'module': 'contacts', 'type': 'a', 'q': 'contact'})
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 1)

    def test_user_isolation(self):
        self.client.logout()
        self.client.login(email='other@example.com', password='pass1234')
        ActivityLog.objects.create(
            user=self.user, activity_type='t', title='User1 only',
        )
        resp = self.client.get(self.url)
        data = json.loads(resp.content)
        self.assertEqual(data['total'], 0)


class ActivityLoggingIntegrationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='integ@example.com', username='integuser', password='pass1234',
        )
        self.client.login(email='integ@example.com', password='pass1234')

    def test_contact_create_logs_activity(self):
        from companies.models import Company
        company = Company.objects.create(owner=self.user, name='Co')
        self.client.post(reverse('contacts:create'), {
            'full_name': 'John Doe',
            'email': 'john@test.com', 'company': company.pk,
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='contact_created').exists(),
        )

    def test_company_create_logs_activity(self):
        self.client.post(reverse('companies:create'), {
            'name': 'NewCorp',
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='company_created').exists(),
        )

    def test_lead_create_logs_activity(self):
        self.client.post(reverse('leads:create'), {
            'lead_name': 'Lead One', 'email': 'lead@test.com',
            'source': 'Website', 'status': 'New', 'priority': 'Medium',
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='lead_created').exists(),
        )

    def test_deal_create_logs_activity(self):
        self.client.post(reverse('deals:create'), {
            'deal_name': 'Big Deal', 'value': 10000, 'stage': 'New',
            'probability': 50,
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='deal_created').exists(),
        )

    def test_task_create_logs_activity(self):
        self.client.post(reverse('tasks:create'), {
            'title': 'Test Task', 'status': 'pending', 'priority': 'high',
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='task_created').exists(),
        )

    def test_campaign_create_logs_activity(self):
        self.client.post(reverse('campaigns:create'), {
            'name': 'Summer Campaign', 'subject': 'Summer Sale',
            'status': 'Draft', 'body': 'Hello!',
        })
        self.assertTrue(
            ActivityLog.objects.filter(activity_type='campaign_created').exists(),
        )
