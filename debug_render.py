import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rittikdesk.settings')
import django
django.setup()
from django.template import engines
from django.test.client import RequestFactory
from django.contrib.auth import get_user_model
User = get_user_model()

from contacts.models import Contact

try:
    user = User.objects.first()
    if not user:
        print('No user found, skipping render test')
    else:
        contact = Contact.objects.filter(owner=user).first()
        if not contact:
            contact = Contact.objects.create(
                owner=user,
                full_name='Test Contact',
                email='test@example.com',
                tags='lead,client',
            )
        
        engine = engines['django']
        template = engine.get_template('contacts/contact_detail.html')
        factory = RequestFactory()
        request = factory.get('/contacts/1/')
        request.user = user
        request.session = {}
        
        rendered = template.render({'contact': contact}, request=request)
        print(f'Rendered OK ({len(rendered)} chars)')
        # Check for common error indicators
        error_indicators = ['error', 'Error', 'ERROR', 'Traceback', 'alert', 'danger']
        for indicator in error_indicators:
            if indicator in rendered:
                pos = rendered.find(indicator)
                print(f'  Found "{indicator}" at position {pos}')
        if 'TemplateSyntaxError' in rendered:
            print('  Found TemplateSyntaxError in output!')
        else:
            print('  No template errors detected')
except Exception as e:
    import traceback
    traceback.print_exc()
