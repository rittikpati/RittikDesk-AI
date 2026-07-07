def contact_summary_prompt(contact):
    return (
        f"You are a CRM assistant. Generate a professional summary of this contact:\n\n"
        f"Name: {contact.full_name}\n"
        f"Company: {contact.company or 'N/A'}\n"
        f"Job Title: {contact.job_title or 'N/A'}\n"
        f"Email: {contact.email or 'N/A'}\n"
        f"Phone: {contact.phone or 'N/A'}\n"
        f"Tags: {contact.tags or 'None'}\n"
        f"Notes: {contact.notes or 'No notes available.'}\n"
        f"Created: {contact.created_at.strftime('%B %d, %Y')}\n"
        f"Last Updated: {contact.updated_at.strftime('%B %d, %Y')}\n\n"
        f"Provide a concise professional summary (3-4 sentences). "
        f"Include their role, company, relevance, and key notes. "
        f"Format in plain text without markdown."
    )


def lead_scoring_prompt(lead):
    return (
        f"You are a CRM assistant. Analyze this lead and provide a score (0-100), "
        f"classification (Hot/Warm/Cold), reasoning, and recommended next action.\n\n"
        f"Lead Name: {lead.lead_name}\n"
        f"Company: {lead.company or 'N/A'}\n"
        f"Contact Person: {lead.contact_person or 'N/A'}\n"
        f"Email: {lead.email or 'N/A'}\n"
        f"Phone: {lead.phone or 'N/A'}\n"
        f"Status: {lead.status}\n"
        f"Priority: {lead.priority}\n"
        f"Source: {lead.source}\n"
        f"Expected Revenue: ${lead.expected_revenue or 0}\n"
        f"Notes: {lead.notes or 'No notes available.'}\n"
        f"Created: {lead.created_at.strftime('%B %d, %Y')}\n"
        f"Last Updated: {lead.updated_at.strftime('%B %d, %Y')}\n\n"
        f"Respond ONLY with a valid JSON object (no markdown, no code fences):\n"
        f'{{\n'
        f'  "score": <0-100>,\n'
        f'  "classification": "<Hot|Warm|Cold>",\n'
        f'  "reasoning": "<2-3 sentence reasoning>",\n'
        f'  "recommended_action": "<specific next action>"\n'
        f'}}'
    )


def email_generator_prompt(contact, email_type):
    prompt = (
        f"You are a CRM assistant. Generate a professional email for this contact.\n\n"
        f"Contact Name: {contact.full_name}\n"
        f"Company: {contact.company or 'N/A'}\n"
        f"Email: {contact.email or 'N/A'}\n"
        f"Notes: {contact.notes or 'N/A'}\n\n"
        f"Email Type: {email_type}\n\n"
    )

    type_instructions = {
        'Introduction': (
            "Write a warm introduction email introducing yourself/your company. "
            "Be professional and friendly. Mention the contact's work if possible."
        ),
        'Follow-up': (
            "Write a polite follow-up email. Reference previous communication "
            "and express continued interest. Keep it concise."
        ),
        'Proposal': (
            "Write a proposal email. Briefly present a solution or offer. "
            "Be persuasive and professional."
        ),
        'Reminder': (
            "Write a gentle reminder email. Be polite and understanding. "
            "Reference any pending items or deadlines."
        ),
        'Thank You': (
            "Write a thank you email expressing gratitude. "
            "Be warm and professional."
        ),
    }

    prompt += type_instructions.get(email_type, "Write a professional email.")
    prompt += (
        "\n\nRespond ONLY with a valid JSON object (no markdown, no code fences):\n"
        '{\n'
        '  "subject": "<email subject line>",\n'
        '  "body": "<full email body with professional tone>"\n'
        '}'
    )
    return prompt


def follow_up_suggestions_prompt(lead):
    return (
        f"You are a CRM assistant. Based on this lead's data, suggest 4 follow-up actions "
        f"with timing and reasoning.\n\n"
        f"Lead Name: {lead.lead_name}\n"
        f"Company: {lead.company or 'N/A'}\n"
        f"Status: {lead.status}\n"
        f"Priority: {lead.priority}\n"
        f"Source: {lead.source}\n"
        f"Expected Revenue: ${lead.expected_revenue or 0}\n"
        f"Notes: {lead.notes or 'No notes available.'}\n\n"
        f"Respond ONLY with a valid JSON object (no markdown, no code fences):\n"
        f'{{\n'
        f'  "suggestions": [\n'
        f'    {{"action": "<specific action>", "timing": "<when>", "reason": "<why>"}},\n'
        f'    {{"action": "...", "timing": "...", "reason": "..."}},\n'
        f'    {{"action": "...", "timing": "...", "reason": "..."}},\n'
        f'    {{"action": "...", "timing": "...", "reason": "..."}}\n'
        f'  ]\n'
        f'}}'
    )


def crm_insights_prompt(stats):
    return (
        f"You are a CRM analytics assistant. Analyze this CRM data and provide "
        f"3 key insights and 3 actionable recommendations.\n\n"
        f"Current CRM Statistics:\n"
        f"- Total Contacts: {stats['total_contacts']}\n"
        f"- Contacts Created This Month: {stats['new_contacts_month']}\n"
        f"- Total Leads: {stats['total_leads']}\n"
        f"- Leads Created This Month: {stats['new_leads_month']}\n"
        f"- Won Leads: {stats['won_leads']}\n"
        f"- Lost Leads: {stats['lost_leads']}\n"
        f"- Leads by Status: New={stats['leads_new']}, Contacted={stats['leads_contacted']}, "
        f"Qualified={stats['leads_qualified']}, Proposal Sent={stats['leads_proposal']}, "
        f"Negotiation={stats['leads_negotiation']}\n"
        f"- High Priority Leads: {stats['high_priority_leads']}\n"
        f"- Recent Contacts (30d): {stats['recent_contacts_30d']}\n"
        f"- Inactive Contacts (90d+): {stats['inactive_contacts_90d']}\n\n"
        f"Respond ONLY with a valid JSON object (no markdown, no code fences):\n"
        f'{{\n'
        f'  "insights": [\n'
        f'    {{"title": "<short title>", "description": "<1-2 sentence insight>"}},\n'
        f'    {{"title": "...", "description": "..."}},\n'
        f'    {{"title": "...", "description": "..."}}\n'
        f'  ],\n'
        f'  "recommendations": [\n'
        f'    {{"action": "<specific action>", "impact": "<expected impact>"}},\n'
        f'    {{"action": "...", "impact": "..."}},\n'
        f'    {{"action": "...", "impact": "..."}}\n'
        f'  ]\n'
        f'}}'
    )


def daily_recommendations_prompt(stats):
    parts = [
        "You are a CRM assistant. Generate 4 daily recommendations based on this data.\n",
        f"\nToday's CRM Stats:\n",
        f"- Total Contacts: {stats['total_contacts']}\n",
        f"- High Priority Leads: {stats['high_priority_leads']}\n",
        f"- Leads Needing Follow-up (Contacted/New): {stats['leads_needing_followup']}\n",
        f"- Inactive Contacts (90d+): {stats['inactive_contacts_90d']}\n",
        f"- Won Leads: {stats['won_leads']}\n",
        f"- Lost Leads: {stats['lost_leads']}\n\n",
        "Recent Contacts:\n",
    ]
    for c in stats['recent_contacts_list']:
        parts.append(f"- {c['name']} ({c['company'] or 'No company'})\n")
    parts.append("\nRecent Leads:\n")
    for l in stats['recent_leads_list']:
        parts.append(f"- {l['name']} ({l['status']}, {l['priority']} priority)\n")
    parts.append(
        "\nGenerate 4 diverse daily recommendations. "
        "Examples: 'Contact John Doe today', 'Follow up with Acme Corp', etc.\n"
        "Respond ONLY with a valid JSON object (no markdown, no code fences):\n"
        '{\n'
        '  "recommendations": [\n'
        '    {"action": "<specific action>", "detail": "<brief detail>", "priority": "<high|medium|low>", "icon": "<fa-icon-name>"},\n'
        '    {"action": "...", "detail": "...", "priority": "...", "icon": "..."},\n'
        '    {"action": "...", "detail": "...", "priority": "...", "icon": "..."},\n'
        '    {"action": "...", "detail": "...", "priority": "...", "icon": "..."}\n'
        '  ]\n'
        '}'
    )
    return "".join(parts)
