from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()


class ConversationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', password='testpass123')
        self.conversation = Conversation.objects.create(user=self.user, title='Test Chat')

    def test_conversation_creation(self):
        self.assertEqual(self.conversation.title, 'Test Chat')
        self.assertEqual(self.conversation.user, self.user)

    def test_message_creation(self):
        Message.objects.create(conversation=self.conversation, role='user', content='Hello')
        Message.objects.create(conversation=self.conversation, role='assistant', content='Hi there')
        self.assertEqual(self.conversation.messages.count(), 2)

    def test_conversation_str(self):
        self.assertEqual(str(self.conversation), 'Test Chat')

    def test_message_str(self):
        msg = Message.objects.create(conversation=self.conversation, role='user', content='Hello world')
        self.assertIn('Hello world', str(msg))

    def test_user_conversation_isolation(self):
        user2 = User.objects.create_user(email='other@example.com', password='testpass123')
        conv2 = Conversation.objects.create(user=user2, title='Other Chat')
        self.assertEqual(Conversation.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Conversation.objects.filter(user=user2).count(), 1)

    def test_conversation_ordering(self):
        from django.utils import timezone
        import datetime
        conv1 = Conversation.objects.create(user=self.user, title='Older')
        Conversation.objects.filter(pk=conv1.pk).update(updated_at=timezone.now() - datetime.timedelta(hours=1))
        conv2 = Conversation.objects.create(user=self.user, title='Newer')
        qs = Conversation.objects.filter(user=self.user)
        self.assertEqual(qs.first(), conv2)
