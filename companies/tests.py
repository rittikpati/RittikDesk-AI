import io
import csv
import tempfile

from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import CustomUser

from .models import Company


class CompanyModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com', username='testuser', password='testpass123'
        )

    def test_create_company(self):
        c = Company.objects.create(
            owner=self.user, name='Test Corp', industry='Technology',
            city='San Francisco', country='USA', employees=500,
        )
        self.assertEqual(c.name, 'Test Corp')
        self.assertEqual(c.industry, 'Technology')
        self.assertEqual(c.status, 'Active')
        self.assertEqual(str(c), 'Test Corp')

    def test_duplicate_name_detection(self):
        Company.objects.create(owner=self.user, name='Unique Corp')
        exists = Company.objects.filter(name__iexact='unique corp').exists()
        self.assertTrue(exists)


class CompanyViewsTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@example.com', username='testuser', password='testpass123'
        )
        self.client.login(email='test@example.com', password='testpass123')
        self.company = Company.objects.create(
            owner=self.user,
            name='Acme Corp',
            industry='Technology',
            city='New York',
            country='USA',
            employees=1000,
            annual_revenue=1000000,
            status='Active',
        )

    def test_list_view(self):
        response = self.client.get(reverse('companies:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Corp')

    def test_create_view(self):
        response = self.client.post(reverse('companies:create'), {
            'name': 'NewCo',
            'industry': 'Finance',
            'city': 'London',
            'country': 'UK',
            'status': 'Active',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Company.objects.filter(name='NewCo').exists())

    def test_create_view_get(self):
        response = self.client.get(reverse('companies:create'))
        self.assertEqual(response.status_code, 200)

    def test_detail_view(self):
        response = self.client.get(reverse('companies:detail', args=[self.company.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Acme Corp')
        self.assertContains(response, 'Technology')

    def test_update_view(self):
        response = self.client.post(
            reverse('companies:update', args=[self.company.pk]),
            {'name': 'Acme Corp Updated', 'industry': 'Technology', 'status': 'Active'},
        )
        self.assertEqual(response.status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.name, 'Acme Corp Updated')

    def test_delete_view_get(self):
        response = self.client.get(reverse('companies:delete', args=[self.company.pk]))
        self.assertEqual(response.status_code, 200)

    def test_delete_view_post(self):
        response = self.client.post(
            reverse('companies:delete', args=[self.company.pk]),
            {'confirm_name': 'Acme Corp'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Company.objects.filter(pk=self.company.pk).exists())

    def test_search_json(self):
        response = self.client.get(reverse('companies:search'), {'search': 'Acme'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['companies']), 1)

    def test_bulk_delete(self):
        c2 = Company.objects.create(owner=self.user, name='ToDelete')
        response = self.client.post(
            reverse('companies:bulk_delete'),
            {'ids': [str(c2.pk)]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Company.objects.filter(pk=c2.pk).exists())

    def test_bulk_update(self):
        c2 = Company.objects.create(owner=self.user, name='ToUpdate')
        response = self.client.post(
            reverse('companies:bulk_update'),
            {'ids': [str(c2.pk)], 'status': 'Inactive'},
        )
        self.assertEqual(response.status_code, 200)
        c2.refresh_from_db()
        self.assertEqual(c2.status, 'Inactive')

    def test_export_csv(self):
        response = self.client.get(reverse('companies:export_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        content = response.content.decode('utf-8')
        self.assertIn('Acme Corp', content)

    def test_export_xlsx(self):
        response = self.client.get(reverse('companies:export_xlsx'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )

    def test_export_pdf(self):
        response = self.client.get(reverse('companies:export_pdf'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_duplicate_detection(self):
        response = self.client.post(reverse('companies:create'), {
            'name': 'Acme Corp',
        })
        self.assertEqual(response.status_code, 200)
        form = response.context['form']
        self.assertFormError(form, 'name', 'A company with this name already exists.')

    def test_owner_isolation(self):
        other_user = CustomUser.objects.create_user(
            email='other@example.com', username='other', password='testpass123'
        )
        other_company = Company.objects.create(owner=other_user, name='Other Corp')
        response = self.client.get(reverse('companies:detail', args=[other_company.pk]))
        self.assertEqual(response.status_code, 404)

    def test_import_csv(self):
        csv_content = 'name,industry,city,country\nImportedCo,Technology,Berlin,Germany\n'
        file = io.BytesIO(csv_content.encode('utf-8'))
        file.name = 'test.csv'
        response = self.client.post(reverse('companies:import'), {'csv_file': file})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Company.objects.filter(name='ImportedCo').exists())
