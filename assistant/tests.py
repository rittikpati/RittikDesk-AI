from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Conversation, Message

User = get_user_model()


class ConversationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@example.com', username='testuser', password='testpass123')
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
        user2 = User.objects.create_user(email='other@example.com', username='other', password='testpass123')
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


class CreateDealActionTest(TestCase):
    """Test enhanced deal creation via chatbot."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='deal@test.com', username='dealtester', password='pass1234',
        )
        from assistant.action_layer import CreateDealAction
        self.action = CreateDealAction()

    def test_create_deal_name_only(self):
        result = self.action.execute('create deal Acme Corp', self.user)
        self.assertIn('Acme Corp', result)
        self.assertIn('created successfully', result)

    def test_create_deal_with_value(self):
        result = self.action.execute('create deal Enterprise worth $50,000', self.user)
        self.assertIn('Enterprise', result)
        self.assertIn('50,000', result)

    def test_create_deal_with_stage(self):
        result = self.action.execute('create deal Big Deal in negotiation', self.user)
        self.assertIn('Big Deal', result)
        self.assertIn('Negotiation', result)

    def test_create_deal_with_priority(self):
        result = self.action.execute('create deal Urgent Deal high priority', self.user)
        self.assertIn('Urgent Deal', result)
        self.assertIn('High', result)

    def test_create_deal_with_company(self):
        result = self.action.execute('create deal Widget Deal for Acme Corp', self.user)
        self.assertIn('Widget Deal', result)
        self.assertIn('Acme Corp', result)

    def test_create_deal_with_all_fields(self):
        result = self.action.execute(
            'create deal Mega Deal worth $100,000 in proposal sent '
            'high priority for TechCorp from LinkedIn probability 75%',
            self.user,
        )
        self.assertIn('Mega Deal', result)
        self.assertIn('100,000', result)
        self.assertIn('Proposal Sent', result)
        self.assertIn('High', result)
        self.assertIn('TechCorp', result)
        self.assertIn('LinkedIn', result)
        self.assertIn('75%', result)

    def test_create_deal_with_k_value(self):
        result = self.action.execute('create deal Quick Deal worth 50k', self.user)
        self.assertIn('Quick Deal', result)
        self.assertIn('50,000', result)

    def test_create_deal_duplicate_name(self):
        from deals.models import Deal
        Deal.objects.create(owner=self.user, deal_name='Existing Deal')
        result = self.action.execute('create deal Existing Deal', self.user)
        self.assertIn('already exists', result)

    def test_create_deal_no_name(self):
        result = self.action.execute('create deal', self.user)
        self.assertIn('need a deal name', result)

    def test_create_deal_owner_isolation(self):
        self.action.execute('create deal My Deal worth $10000', self.user)
        from deals.models import Deal
        self.assertEqual(Deal.objects.filter(owner=self.user).count(), 1)


class UpdateDealActionTest(TestCase):
    """Test enhanced deal update via chatbot."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='dealupd@test.com', username='dealupd', password='pass1234',
        )
        from deals.models import Deal
        self.deal = Deal.objects.create(
            owner=self.user, deal_name='Update Test Deal',
            value=10000, stage='New', priority='Medium',
        )
        from assistant.action_layer import UpdateDealAction
        self.action = UpdateDealAction()

    def test_update_stage(self):
        result = self.action.execute('move Update Test Deal to negotiation', self.user)
        self.assertIn('stage changed', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.stage, 'Negotiation')

    def test_update_value(self):
        result = self.action.execute('set value to $25,000 for Update Test Deal', self.user)
        self.assertIn('value updated', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.value, 25000)

    def test_update_priority(self):
        result = self.action.execute('change priority to high for Update Test Deal', self.user)
        self.assertIn('priority set', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.priority, 'High')

    def test_update_company(self):
        result = self.action.execute('set company to Acme Corp for Update Test Deal', self.user)
        self.assertIn('company set', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.company, 'Acme Corp')

    def test_update_source(self):
        result = self.action.execute('change source to linkedin for Update Test Deal', self.user)
        self.assertIn('source set', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.source, 'LinkedIn')

    def test_update_probability(self):
        result = self.action.execute('set probability to 75 for Update Test Deal', self.user)
        self.assertIn('probability set', result)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.probability, 75)

    def test_update_multiple_fields(self):
        result = self.action.execute(
            'Update Test Deal to won value to $50000 priority high',
            self.user,
        )
        self.assertIn('stage changed', result)
        self.assertIn('value updated', result)
        self.assertIn('priority set', result)

    def test_update_deal_not_found(self):
        result = self.action.execute('update Nonexistent Deal to won', self.user)
        self.assertIn('not found', result)

    def test_update_no_changes(self):
        result = self.action.execute('update Update Test Deal', self.user)
        self.assertIn('No changes', result)


class DeleteDealActionTest(TestCase):
    """Test deal deletion via chatbot."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='dealdel@test.com', username='dealdel', password='pass1234',
        )
        from deals.models import Deal
        self.deal = Deal.objects.create(
            owner=self.user, deal_name='Delete Test Deal',
            value=5000, stage='New',
        )
        from assistant.action_layer import DeleteDealAction
        self.action = DeleteDealAction()

    def test_delete_deal(self):
        result = self.action.execute('delete deal Delete Test Deal', self.user)
        self.assertIn('deleted successfully', result)
        from deals.models import Deal
        self.assertFalse(Deal.objects.filter(pk=self.deal.pk).exists())

    def test_delete_deal_not_found(self):
        result = self.action.execute('delete deal Nonexistent Deal', self.user)
        self.assertIn('not found', result)

    def test_delete_deal_owner_isolation(self):
        other_user = User.objects.create_user(
            email='other@test.com', username='otherdel', password='pass1234',
        )
        from deals.models import Deal
        other_deal = Deal.objects.create(
            owner=other_user, deal_name='Other User Deal',
        )
        result = self.action.execute('delete deal Other User Deal', self.user)
        self.assertIn('not found', result)
        self.assertTrue(Deal.objects.filter(pk=other_deal.pk).exists())
