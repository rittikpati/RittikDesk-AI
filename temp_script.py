import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rittikdesk.settings')
import django
django.setup()
from calendars.models import Event

all_events = Event.objects.all().select_related('owner')
print(f'Total events: {all_events.count()}')
for e in all_events:
    print(f'  ID={e.id}, owner_id={e.owner_id}, owner={e.owner.username}, title="{e.title}", date={e.start_date}, status={e.status}')

print()
u1_events = Event.objects.filter(owner_id=1)
print(f'Events for user_id=1: {u1_events.count()}')
for e in u1_events:
    print(f'  ID={e.id}, title="{e.title}", date={e.start_date}')
