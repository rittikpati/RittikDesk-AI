from django.test import TestCase, Client
from django.urls import reverse


class CoreTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_landing_page_loads(self):
        response = self.client.get(reverse('core:landing'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/landing.html')

    def test_health_check(self):
        response = self.client.get(reverse('core:health'))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'healthy', 'version': '1.0.0'})
