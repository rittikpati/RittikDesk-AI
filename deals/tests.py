from django.test import TestCase, Client
from django.urls import reverse
from .models import Deal
from accounts.models import CustomUser


class DealModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com', username='testuser', password='pass1234',
        )

    def test_create_deal(self):
        deal = Deal.objects.create(
            owner=self.user,
            deal_name='Test Deal',
            value=10000,
            stage='New',
        )
        self.assertEqual(deal.status, 'Open')
        self.assertEqual(str(deal), 'Test Deal')

    def test_update_status_from_stage(self):
        deal = Deal.objects.create(owner=self.user, deal_name='Won Deal', stage='Won')
        self.assertEqual(deal.status, 'Won')

        deal2 = Deal.objects.create(owner=self.user, deal_name='Lost Deal', stage='Lost')
        self.assertEqual(deal2.status, 'Lost')

        deal3 = Deal.objects.create(owner=self.user, deal_name='Open Deal', stage='Negotiation')
        self.assertEqual(deal3.status, 'Open')


class DealViewsTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com', username='testuser', password='pass1234',
        )
        self.client = Client()
        self.client.login(email='test@example.com', password='pass1234')
        self.deal = Deal.objects.create(
            owner=self.user,
            deal_name='Rahul Sharma Deal',
            value=8000,
            stage='New',
        )

    def test_list_view(self):
        resp = self.client.get(reverse('deals:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rahul Sharma Deal')

    def test_create_view(self):
        resp = self.client.get(reverse('deals:create'))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('deals:create'), {
            'deal_name': 'New Deal',
            'value': '5000',
            'stage': 'New',
            'probability': '50',
        })
        self.assertRedirects(resp, reverse('deals:list'))
        self.assertTrue(Deal.objects.filter(deal_name='New Deal').exists())

    def test_detail_view(self):
        resp = self.client.get(reverse('deals:detail', args=[self.deal.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Rahul Sharma Deal')

    def test_update_view(self):
        resp = self.client.get(reverse('deals:update', args=[self.deal.pk]))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('deals:update', args=[self.deal.pk]), {
            'deal_name': 'Rahul Sharma Deal',
            'value': '8000',
            'stage': 'Negotiation',
            'probability': '80',
        })
        self.assertRedirects(resp, reverse('deals:list'))
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'Negotiation')

    def test_delete_view(self):
        resp = self.client.get(reverse('deals:delete', args=[self.deal.pk]))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('deals:delete', args=[self.deal.pk]), {'confirm': 'delete'})
        self.assertRedirects(resp, reverse('deals:list'))
        self.assertFalse(Deal.objects.filter(pk=self.deal.pk).exists())

    def test_kanban_view(self):
        resp = self.client.get(reverse('deals:kanban'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Pipeline')

    def test_search_json(self):
        resp = self.client.get(reverse('deals:search'), {'search': 'Rahul'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['count'], 1)

    def test_bulk_delete(self):
        resp = self.client.post(reverse('deals:bulk_delete'), {'ids': [self.deal.pk]})
        self.assertEqual(resp.status_code, 200)

    def test_bulk_update(self):
        resp = self.client.post(reverse('deals:bulk_update'), {'ids': [self.deal.pk], 'stage': 'Qualified'})
        self.assertEqual(resp.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'Qualified')

    def test_export_csv(self):
        resp = self.client.get(reverse('deals:export_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])

    def test_export_xlsx(self):
        resp = self.client.get(reverse('deals:export_xlsx'))
        self.assertEqual(resp.status_code, 200)

    def test_export_pdf(self):
        resp = self.client.get(reverse('deals:export_pdf'))
        self.assertEqual(resp.status_code, 200)

    def test_kanban_update(self):
        resp = self.client.post(reverse('deals:kanban_update'), {
            'deal_id': self.deal.pk,
            'stage': 'Negotiation',
        })
        self.assertEqual(resp.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'Negotiation')

    def test_owner_isolation(self):
        other_user = CustomUser.objects.create_user(email='other@example.com', username='otheruser', password='pass1234')
        other_deal = Deal.objects.create(owner=other_user, deal_name='Other Deal')
        resp = self.client.get(reverse('deals:detail', args=[other_deal.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_duplicate_detection(self):
        resp = self.client.post(reverse('deals:create'), {
            'deal_name': 'Rahul Sharma Deal',
            'value': '5000',
            'stage': 'New',
        })
        self.assertEqual(resp.status_code, 200)  # form re-rendered with errors
        form = resp.context.get('form')
        self.assertIsNotNone(form)
        self.assertTrue(form.errors.get('deal_name'))
