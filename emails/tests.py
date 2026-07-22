from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from contacts.models import Contact
from leads.models import Lead
from .models import SMTPConfig, EmailMessage, EmailTemplate


User = get_user_model()


class EmailsAppTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
        )
        cls.user2 = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123',
        )

    def setUp(self):
        self.client = Client()
        self.client.login(email='test@example.com', password='testpass123')

    # ── SMTP Config ──

    def test_smtp_config_view(self):
        resp = self.client.get(reverse('emails:smtp_config'))
        self.assertEqual(resp.status_code, 200)

    def test_smtp_config_save(self):
        resp = self.client.post(reverse('emails:smtp_save'), {
            'host': 'smtp.example.com',
            'port': 587,
            'encryption': 'tls',
            'username': 'me@example.com',
            'password': 'secret',
            'sender_name': 'Me',
            'sender_email': '',
        })
        self.assertRedirects(resp, reverse('emails:smtp_config'))
        self.assertTrue(SMTPConfig.objects.filter(owner=self.user).exists())
        config = SMTPConfig.objects.get(owner=self.user)
        self.assertEqual(config.host, 'smtp.example.com')

    def test_smtp_config_isolation(self):
        """User2 should not see user's SMTP config."""
        SMTPConfig.objects.create(owner=self.user, host='smtp.foo.com',
                                  username='u@foo.com', password='p')
        self.client.login(email='other@example.com', password='testpass123')
        resp = self.client.get(reverse('emails:smtp_config'))
        self.assertNotContains(resp, 'smtp.foo.com')

    # ── Compose ──

    def test_compose_view(self):
        resp = self.client.get(reverse('emails:compose'))
        self.assertEqual(resp.status_code, 200)

    def test_compose_save_draft(self):
        resp = self.client.post(reverse('emails:compose'), {
            'to_emails': 'recipient@example.com',
            'subject': 'Test Subject',
            'body_plain': 'Hello world',
            'priority': 'normal',
            'action': 'draft',
        })
        if resp.status_code == 200 and resp.context and 'form' in resp.context:
            self.fail(f'Form errors: {resp.context["form"].errors}')
        self.assertRedirects(resp, reverse('emails:sent'))
        self.assertTrue(EmailMessage.objects.filter(owner=self.user, is_draft=True).exists())

    def test_compose_requires_to(self):
        resp = self.client.post(reverse('emails:compose'), {
            'to_emails': '',
            'subject': 'Test',
            'body_plain': 'Body',
            'action': 'draft',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EmailMessage.objects.filter(owner=self.user).exists())

    # ── Sent list ──

    def test_sent_list_view(self):
        EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='S1', status='sent',
        )
        resp = self.client.get(reverse('emails:sent'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'S1')

    def test_sent_list_isolation(self):
        EmailMessage.objects.create(
            owner=self.user2, to_emails='a@b.com', subject='Other Email', status='sent',
        )
        resp = self.client.get(reverse('emails:sent'))
        self.assertNotContains(resp, 'Other Email')

    # ── Drafts ──

    def test_draft_list_view(self):
        EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='Draft1',
            is_draft=True, status='draft',
        )
        resp = self.client.get(reverse('emails:drafts'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Draft1')

    def test_draft_isolation(self):
        EmailMessage.objects.create(
            owner=self.user2, to_emails='a@b.com', subject='Other Draft',
            is_draft=True, status='draft',
        )
        resp = self.client.get(reverse('emails:drafts'))
        self.assertNotContains(resp, 'Other Draft')

    # ── Detail ──

    def test_email_detail_view(self):
        email = EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='Detail Test',
        )
        resp = self.client.get(reverse('emails:detail', args=[email.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Detail Test')

    def test_email_detail_isolation(self):
        email = EmailMessage.objects.create(
            owner=self.user2, to_emails='a@b.com', subject='Not Mine',
        )
        resp = self.client.get(reverse('emails:detail', args=[email.pk]))
        self.assertEqual(resp.status_code, 404)

    # ── Cancel / Retry ──

    def test_cancel_queued_email(self):
        email = EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='Cancel Me',
            status='queued',
        )
        resp = self.client.post(reverse('emails:cancel', args=[email.pk]))
        self.assertRedirects(resp, reverse('emails:sent'))
        email.refresh_from_db()
        self.assertEqual(email.status, 'cancelled')

    def test_retry_failed_email(self):
        email = EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='Retry Me',
            status='failed',
        )
        resp = self.client.post(reverse('emails:retry', args=[email.pk]))
        self.assertRedirects(resp, reverse('emails:sent'))
        email.refresh_from_db()

    # ── Templates ──

    def test_template_crud(self):
        resp = self.client.post(reverse('emails:template_create'), {
            'name': 'Welcome',
            'subject': 'Welcome!',
            'body_html': '<p>Hi</p>',
        })
        self.assertRedirects(resp, reverse('emails:templates'))
        self.assertTrue(EmailTemplate.objects.filter(owner=self.user, name='Welcome').exists())

        tpl = EmailTemplate.objects.get(owner=self.user, name='Welcome')
        resp = self.client.post(reverse('emails:template_update', args=[tpl.pk]), {
            'name': 'Welcome Updated',
            'subject': 'Welcome!',
            'body_html': '<p>Hi</p>',
        })
        self.assertRedirects(resp, reverse('emails:templates'))
        tpl.refresh_from_db()
        self.assertEqual(tpl.name, 'Welcome Updated')

    def test_template_json_endpoint(self):
        tpl = EmailTemplate.objects.create(
            owner=self.user, name='Test', subject='Test Subj',
            body_html='<p>Body</p>',
        )
        resp = self.client.get(reverse('emails:template_json', args=[tpl.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['subject'], 'Test Subj')

    # ── Stats endpoint ──

    def test_stats_json(self):
        EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='S1', status='sent',
        )
        EmailMessage.objects.create(
            owner=self.user, to_emails='a@b.com', subject='D1',
            is_draft=True, status='draft',
        )
        resp = self.client.get(reverse('emails:stats_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['total'], 2)
        self.assertEqual(data['sent'], 1)
        self.assertEqual(data['drafts'], 1)
