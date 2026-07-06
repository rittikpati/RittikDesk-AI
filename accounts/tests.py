from django.test import TestCase, Client
from django.urls import reverse
from .models import CustomUser


class AccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_register_page_loads(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/login.html')

    def test_registration_creates_user(self):
        response = self.client.post(reverse('accounts:register'), {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CustomUser.objects.filter(email='newuser@example.com').exists())

    def test_login_authenticates(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'test@example.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)

    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)

    def test_profile_loads_when_logged_in(self):
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/profile.html')
