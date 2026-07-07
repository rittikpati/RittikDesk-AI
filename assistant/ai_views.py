import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from contacts.models import Contact
from leads.models import Lead
from .services.ai_crm_service import AICRMService
from .services.exceptions import AIAssistantError

logger = logging.getLogger(__name__)


class ContactAISummaryView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        contact = get_object_or_404(Contact, pk=pk, owner=request.user)
        try:
            service = AICRMService()
            summary = service.contact_summary(contact)
            return JsonResponse({'summary': summary})
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
        except Exception as e:
            logger.exception('Contact AI summary failed')
            return JsonResponse({'error': 'Failed to generate summary.'}, status=500)


class LeadAIScoreView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        try:
            service = AICRMService()
            result = service.lead_score(lead)
            return JsonResponse(result)
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
        except Exception as e:
            logger.exception('Lead AI score failed')
            return JsonResponse({'error': 'Failed to analyze lead.'}, status=500)


class GenerateEmailView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request):
        contact_id = request.POST.get('contact_id')
        email_type = request.POST.get('email_type', 'Introduction')

        if not contact_id:
            return JsonResponse({'error': 'Contact ID is required.'}, status=400)

        valid_types = ['Introduction', 'Follow-up', 'Proposal', 'Reminder', 'Thank You']
        if email_type not in valid_types:
            return JsonResponse({'error': 'Invalid email type.'}, status=400)

        contact = get_object_or_404(Contact, pk=contact_id, owner=request.user)
        try:
            service = AICRMService()
            result = service.generate_email(contact, email_type)
            return JsonResponse(result)
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
        except Exception as e:
            logger.exception('Email generation failed')
            return JsonResponse({'error': 'Failed to generate email.'}, status=500)


class FollowUpSuggestionsView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk, owner=request.user)
        try:
            service = AICRMService()
            suggestions = service.follow_up_suggestions(lead)
            return JsonResponse({'suggestions': suggestions})
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
        except Exception as e:
            logger.exception('Follow-up suggestions failed')
            return JsonResponse({'error': 'Failed to generate suggestions.'}, status=500)


class CRMInsightsView(LoginRequiredMixin, View):
    http_method_names = ['get', 'post']

    def get_crm_stats(self, user):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        contacts = Contact.objects.filter(owner=user)
        leads = Lead.objects.filter(owner=user)

        total_contacts = contacts.count()
        new_contacts_month = contacts.filter(created_at__gte=month_start).count()
        recent_contacts_30d = contacts.filter(created_at__gte=thirty_days_ago).count()
        inactive_contacts_90d = contacts.filter(updated_at__lte=ninety_days_ago).count()

        total_leads = leads.count()
        new_leads_month = leads.filter(created_at__gte=month_start).count()
        won_leads = leads.filter(status='Won').count()
        lost_leads = leads.filter(status='Lost').count()
        high_priority_leads = leads.filter(priority__in=['High', 'Urgent']).count()
        leads_needing_followup = leads.filter(status__in=['New', 'Contacted']).count()

        leads_new = leads.filter(status='New').count()
        leads_contacted = leads.filter(status='Contacted').count()
        leads_qualified = leads.filter(status='Qualified').count()
        leads_proposal = leads.filter(status='Proposal Sent').count()
        leads_negotiation = leads.filter(status='Negotiation').count()

        return {
            'total_contacts': total_contacts,
            'new_contacts_month': new_contacts_month,
            'recent_contacts_30d': recent_contacts_30d,
            'inactive_contacts_90d': inactive_contacts_90d,
            'total_leads': total_leads,
            'new_leads_month': new_leads_month,
            'won_leads': won_leads,
            'lost_leads': lost_leads,
            'high_priority_leads': high_priority_leads,
            'leads_needing_followup': leads_needing_followup,
            'leads_new': leads_new,
            'leads_contacted': leads_contacted,
            'leads_qualified': leads_qualified,
            'leads_proposal': leads_proposal,
            'leads_negotiation': leads_negotiation,
        }

    def get(self, request):
        stats = self.get_crm_stats(request.user)
        return JsonResponse(stats)

    def post(self, request):
        stats = self.get_crm_stats(request.user)
        try:
            service = AICRMService()
            result = service.crm_insights(stats)
            result['stats'] = stats
            return JsonResponse(result)
        except AIAssistantError as e:
            return JsonResponse({'error': str(e), 'stats': stats}, status=503)
        except Exception as e:
            logger.exception('CRM insights failed')
            return JsonResponse({'error': 'Failed to generate insights.', 'stats': stats}, status=500)


class DailyRecommendationsView(LoginRequiredMixin, View):
    http_method_names = ['get', 'post']

    def get_crm_stats(self, user):
        now = timezone.now()
        ninety_days_ago = now - timedelta(days=90)

        contacts = Contact.objects.filter(owner=user)
        leads = Lead.objects.filter(owner=user)

        total_contacts = contacts.count()
        high_priority_leads = leads.filter(priority__in=['High', 'Urgent']).count()
        leads_needing_followup = leads.filter(status__in=['New', 'Contacted']).count()
        inactive_contacts_90d = contacts.filter(updated_at__lte=ninety_days_ago).count()
        won_leads = leads.filter(status='Won').count()
        lost_leads = leads.filter(status='Lost').count()

        recent_contacts = contacts.order_by('-created_at')[:5]
        recent_contacts_list = [
            {'name': c.full_name, 'company': c.company}
            for c in recent_contacts
        ]

        recent_leads = leads.order_by('-created_at')[:5]
        recent_leads_list = [
            {'name': l.lead_name, 'status': l.status, 'priority': l.priority}
            for l in recent_leads
        ]

        return {
            'total_contacts': total_contacts,
            'high_priority_leads': high_priority_leads,
            'leads_needing_followup': leads_needing_followup,
            'inactive_contacts_90d': inactive_contacts_90d,
            'won_leads': won_leads,
            'lost_leads': lost_leads,
            'recent_contacts_list': recent_contacts_list,
            'recent_leads_list': recent_leads_list,
        }

    def get(self, request):
        stats = self.get_crm_stats(request.user)
        return JsonResponse(stats)

    def post(self, request):
        stats = self.get_crm_stats(request.user)
        try:
            service = AICRMService()
            recommendations = service.daily_recommendations(stats)
            return JsonResponse({'recommendations': recommendations, 'stats': stats})
        except AIAssistantError as e:
            return JsonResponse({'error': str(e)}, status=503)
        except Exception as e:
            logger.exception('Daily recommendations failed')
            return JsonResponse({'error': 'Failed to generate recommendations.'}, status=500)
