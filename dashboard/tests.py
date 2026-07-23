from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import CustomUser
from contacts.models import Contact
from companies.models import Company
from leads.models import Lead
from deals.models import Deal
from tasks.models import Task
from campaigns.models import Campaign
from emails.models import EmailMessage


class GlobalSearchViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', email='test@test.com', password='testpass123')
        self.other = CustomUser.objects.create_user(username='otheruser', email='other@test.com', password='otherpass123')
        self.client = Client()
        self.client.login(email='test@test.com', password='testpass123')
        self.url = reverse('dashboard:global_search')

        self.contact = Contact.objects.create(owner=self.user, full_name='Rahul Sharma', email='rahul@gmail.com')
        self.company = Company.objects.create(owner=self.user, name='Google', industry='Technology')
        self.lead = Lead.objects.create(owner=self.user, lead_name='John Smith Lead', email='john@lead.com')
        self.deal = Deal.objects.create(owner=self.user, deal_name='Enterprise Plan', value=50000)
        self.task = Task.objects.create(owner=self.user, title='Call Rahul')
        self.campaign = Campaign.objects.create(owner=self.user, name='Summer Campaign', subject='Summer Sale')
        self.email = EmailMessage.objects.create(owner=self.user, subject='Welcome Email', to_emails='user@test.com')

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(self.url, {'q': 'test'})
        self.assertEqual(resp.status_code, 302)

    def test_short_query_returns_empty(self):
        resp = self.client.get(self.url, {'q': 'a'})
        data = resp.json()
        self.assertEqual(data['results'], {})
        self.assertEqual(data['query'], 'a')

    def test_empty_query_returns_empty(self):
        resp = self.client.get(self.url, {'q': ''})
        data = resp.json()
        self.assertEqual(data['results'], {})

    def test_search_contacts(self):
        resp = self.client.get(self.url, {'q': 'Rahul'})
        data = resp.json()
        self.assertEqual(len(data['results']['contacts']), 1)
        self.assertEqual(data['results']['contacts'][0]['name'], 'Rahul Sharma')
        self.assertIn('rahul@gmail.com', data['results']['contacts'][0]['subtitle'])
        self.assertEqual(data['results']['contacts'][0]['detail_url'], f'/contacts/{self.contact.pk}/')

    def test_search_companies(self):
        resp = self.client.get(self.url, {'q': 'Google'})
        data = resp.json()
        self.assertEqual(len(data['results']['companies']), 1)
        self.assertEqual(data['results']['companies'][0]['name'], 'Google')
        self.assertEqual(data['results']['companies'][0]['detail_url'], f'/companies/{self.company.pk}/')

    def test_search_leads(self):
        resp = self.client.get(self.url, {'q': 'John Smith'})
        data = resp.json()
        self.assertEqual(len(data['results']['leads']), 1)
        self.assertEqual(data['results']['leads'][0]['name'], 'John Smith Lead')
        self.assertEqual(data['results']['leads'][0]['detail_url'], f'/leads/{self.lead.pk}/')

    def test_search_deals(self):
        resp = self.client.get(self.url, {'q': 'Enterprise'})
        data = resp.json()
        self.assertEqual(len(data['results']['deals']), 1)
        self.assertEqual(data['results']['deals'][0]['name'], 'Enterprise Plan')
        self.assertEqual(data['results']['deals'][0]['detail_url'], f'/deals/{self.deal.pk}/')

    def test_search_tasks(self):
        resp = self.client.get(self.url, {'q': 'Call Rahul'})
        data = resp.json()
        self.assertEqual(len(data['results']['tasks']), 1)
        self.assertEqual(data['results']['tasks'][0]['name'], 'Call Rahul')
        self.assertEqual(data['results']['tasks'][0]['detail_url'], f'/tasks/{self.task.pk}/')

    def test_search_campaigns(self):
        resp = self.client.get(self.url, {'q': 'Summer'})
        data = resp.json()
        self.assertEqual(len(data['results']['campaigns']), 1)
        self.assertEqual(data['results']['campaigns'][0]['name'], 'Summer Campaign')
        self.assertEqual(data['results']['campaigns'][0]['detail_url'], f'/campaigns/{self.campaign.pk}/')

    def test_search_emails(self):
        resp = self.client.get(self.url, {'q': 'Welcome'})
        data = resp.json()
        self.assertEqual(len(data['results']['emails']), 1)
        self.assertEqual(data['results']['emails'][0]['name'], 'Welcome Email')
        self.assertEqual(data['results']['emails'][0]['detail_url'], f'/emails/{self.email.pk}/')

    def test_no_permission_leakage(self):
        other_contact = Contact.objects.create(owner=self.other, full_name='Secret Person', email='secret@other.com')
        resp = self.client.get(self.url, {'q': 'Secret'})
        data = resp.json()
        self.assertEqual(len(data['results']['contacts']), 0)

    def test_no_permission_leakage_company(self):
        Company.objects.create(owner=self.other, name='Secret Corp')
        resp = self.client.get(self.url, {'q': 'Secret Corp'})
        data = resp.json()
        self.assertEqual(len(data['results']['companies']), 0)

    def test_no_permission_leakage_lead(self):
        Lead.objects.create(owner=self.other, lead_name='Secret Lead')
        resp = self.client.get(self.url, {'q': 'Secret Lead'})
        data = resp.json()
        self.assertEqual(len(data['results']['leads']), 0)

    def test_no_permission_leakage_deal(self):
        Deal.objects.create(owner=self.other, deal_name='Secret Deal')
        resp = self.client.get(self.url, {'q': 'Secret Deal'})
        data = resp.json()
        self.assertEqual(len(data['results']['deals']), 0)

    def test_no_permission_leakage_task(self):
        Task.objects.create(owner=self.other, title='Secret Task')
        resp = self.client.get(self.url, {'q': 'Secret Task'})
        data = resp.json()
        self.assertEqual(len(data['results']['tasks']), 0)

    def test_no_permission_leakage_campaign(self):
        Campaign.objects.create(owner=self.other, name='Secret Campaign', subject='Secret')
        resp = self.client.get(self.url, {'q': 'Secret Campaign'})
        data = resp.json()
        self.assertEqual(len(data['results']['campaigns']), 0)

    def test_no_permission_leakage_email(self):
        EmailMessage.objects.create(owner=self.other, subject='Secret Email', to_emails='x@x.com')
        resp = self.client.get(self.url, {'q': 'Secret Email'})
        data = resp.json()
        self.assertEqual(len(data['results']['emails']), 0)

    def test_cross_module_search(self):
        resp = self.client.get(self.url, {'q': 'Rahul'})
        data = resp.json()
        contact_names = [c['name'] for c in data['results'].get('contacts', [])]
        task_names = [t['name'] for t in data['results'].get('tasks', [])]
        self.assertIn('Rahul Sharma', contact_names)
        self.assertIn('Call Rahul', task_names)

    def test_limit_per_module(self):
        for i in range(10):
            Contact.objects.create(owner=self.user, full_name=f'Test Contact {i}', email=f'test{i}@mail.com')
        resp = self.client.get(self.url, {'q': 'Test Contact'})
        data = resp.json()
        self.assertLessEqual(len(data['results']['contacts']), 5)

    def test_case_insensitive(self):
        resp = self.client.get(self.url, {'q': 'RAHUL'})
        data = resp.json()
        self.assertGreater(len(data['results']['contacts']), 0)

    def test_returns_all_groups(self):
        resp = self.client.get(self.url, {'q': 'test'})
        data = resp.json()
        self.assertIn('contacts', data['results'])
        self.assertIn('companies', data['results'])
        self.assertIn('leads', data['results'])
        self.assertIn('deals', data['results'])
        self.assertIn('tasks', data['results'])
        self.assertIn('campaigns', data['results'])
        self.assertIn('emails', data['results'])

    def test_json_response_format(self):
        resp = self.client.get(self.url, {'q': 'Google'})
        data = resp.json()
        self.assertIn('results', data)
        self.assertIn('query', data)
        self.assertEqual(data['query'], 'Google')
        for module_items in data['results'].values():
            for item in module_items:
                self.assertIn('id', item)
                self.assertIn('name', item)
                self.assertIn('subtitle', item)
                self.assertIn('icon', item)
                self.assertIn('detail_url', item)

    def test_no_duplicate_results(self):
        resp = self.client.get(self.url, {'q': 'Rahul'})
        data = resp.json()
        seen_urls = set()
        for module, items in data['results'].items():
            for item in items:
                url = item['detail_url']
                self.assertNotIn(url, seen_urls)
                seen_urls.add(url)

    def test_no_console_error_on_empty_results(self):
        resp = self.client.get(self.url, {'q': 'zzzznonexistent'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        total = sum(len(items) for items in data['results'].values())
        self.assertEqual(total, 0)
