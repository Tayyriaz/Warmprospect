#!/usr/bin/env python3
"""Create GoAccel business configuration with all fields filled"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config.business_config import config_manager

# GoAccel business configuration
business_config = {
    "business_id": "goaccel-website",
    "business_name": "GoAccel",
    "system_prompt": """You are the AI concierge for GoAccel, an all-in-one growth and operations system for home services and skilled trade businesses.

YOUR ROLE:
Help potential customers understand how GoAccel can accelerate their home services business growth. Be friendly, knowledgeable, and solution-focused. Your goal is to qualify leads, understand their business needs, and guide them toward scheduling a demo or speaking with our sales team.

CONVERSATION APPROACH:
- Use the Knowledge Base (Context) as your primary source of information about GoAccel's services, features, and solutions
- When Context is provided, answer ONLY from that information and cite sources
- If Context doesn't contain the answer, acknowledge that you don't have that specific information and offer to connect them with someone who does
- Ask qualifying questions to understand their business type, current challenges, and growth goals
- Focus on how GoAccel can help them achieve predictable growth and build business value
- Guide conversations toward scheduling a demo or connecting with sales when appropriate

TONE & STYLE:
- Warm, professional, and consultative
- Use contractions and natural language
- Be concise but thorough
- Show genuine interest in helping their business succeed""",
    "primary_goal": "Help home services businesses scale predictably and build long-term enterprise value",
    "personality": "Friendly, knowledgeable, and growth-focused",
    "greeting_message": "Hi! Welcome to GoAccel. I'm here to help you understand how we can accelerate your home services business growth. How can I assist you today?",
    "appointment_link": "https://warmprospect.com/goaccel-website/",
    "privacy_statement": "We collect your information only to provide better service and connect you with the right solutions for your business. Your data is secure and will not be shared with third parties.",
    "website_url": "https://warmprospect.com/goaccel-website/",
    "contact_email": "info@goaccel.com",
    "contact_phone": "855.915.0747",
    "theme_color": "#667eea",
    "widget_position": "center",
    "chatbot_button_text": "Send",
    "voice_enabled": False,
    "cta_tree": {
        "main_menu": {
            "id": "main_menu",
            "label": "What can I help you with?",
            "action": "show_children",
            "children": ["book_appointment", "learn_services", "pricing_info", "contact_sales"]
        },
        "book_appointment": {
            "id": "book_appointment",
            "label": "📅 Book a Free Consultation",
            "action": "link",
            "url": "https://calendly.com/goaccel/growth-call"
        },
        "learn_services": {
            "id": "learn_services",
            "label": "Learn About Our Services",
            "action": "show_children",
            "children": ["agency_services", "software_solutions", "marketing_services"]
        },
        "agency_services": {
            "id": "agency_services",
            "label": "Digital Agency Services",
            "action": "show_children",
            "children": ["wordpress_design", "appointment_booking", "gbp_optimization", "lead_generation"]
        },
        "wordpress_design": {
            "id": "wordpress_design",
            "label": "WordPress Website Design",
            "action": "send",
            "message": "Tell me about your WordPress website design services"
        },
        "appointment_booking": {
            "id": "appointment_booking",
            "label": "Managed Appointment Booking",
            "action": "send",
            "message": "How does your managed appointment booking service work?"
        },
        "gbp_optimization": {
            "id": "gbp_optimization",
            "label": "Google Business Profile Optimization",
            "action": "send",
            "message": "I want to learn about Google Business Profile optimization"
        },
        "lead_generation": {
            "id": "lead_generation",
            "label": "Custom Lead Generation",
            "action": "send",
            "message": "Tell me about your lead generation services"
        },
        "software_solutions": {
            "id": "software_solutions",
            "label": "Software Solutions",
            "action": "show_children",
            "children": ["crm_software", "marketing_automation", "business_management"]
        },
        "crm_software": {
            "id": "crm_software",
            "label": "CRM & Pipeline Management",
            "action": "send",
            "message": "I want to learn about your CRM software and deal pipeline management"
        },
        "marketing_automation": {
            "id": "marketing_automation",
            "label": "Marketing Automation",
            "action": "send",
            "message": "How does your marketing automation platform work?"
        },
        "business_management": {
            "id": "business_management",
            "label": "Business Management Software",
            "action": "send",
            "message": "Tell me about your business management software features"
        },
        "marketing_services": {
            "id": "marketing_services",
            "label": "Marketing & Growth Services",
            "action": "show_children",
            "children": ["review_management", "data_enhancement", "listing_management"]
        },
        "review_management": {
            "id": "review_management",
            "label": "Customer Review Management",
            "action": "send",
            "message": "How do you help manage customer reviews?"
        },
        "data_enhancement": {
            "id": "data_enhancement",
            "label": "Data Enhancement & Reactivation",
            "action": "send",
            "message": "Tell me about your data enhancement and database reactivation services"
        },
        "listing_management": {
            "id": "listing_management",
            "label": "Business Listing Management",
            "action": "send",
            "message": "I want to learn about business listing management"
        },
        "pricing_info": {
            "id": "pricing_info",
            "label": "Pricing & Plans",
            "action": "send",
            "message": "What are your pricing options and plans?"
        },
        "contact_sales": {
            "id": "contact_sales",
            "label": "📞 Contact Sales Team",
            "action": "send",
            "message": "I'd like to speak with your sales team"
        }
    }
}

print("Creating GoAccel business configuration...")
print(f"Business ID: {business_config['business_id']}")
print(f"Business Name: {business_config['business_name']}")
print(f"Website URL: {business_config['website_url']}")

try:
    config = config_manager.create_or_update_business(**business_config)
    print("\n✅ GoAccel business created successfully!")
    print(f"\nConfiguration saved:")
    print(f"  - Business ID: {config['business_id']}")
    print(f"  - Business Name: {config['business_name']}")
    print(f"  - Website URL: {config.get('website_url', 'N/A')}")
    print(f"  - Theme Color: {config.get('theme_color', 'N/A')}")
    print(f"  - Chat Button Text: {config.get('chatbot_button_text', 'Send')}")
    print(f"  - Voice Enabled: {config.get('voice_enabled', False)}")
    print(f"\n📝 Next steps:")
    print(f"  1. Test chatbot: http://localhost:8000/bot?business_id=goaccel-website")
    print(f"  2. Admin page: http://localhost:8000/admin")
    print(f"  3. To build knowledge base, use 'Build KB' button in admin panel")
    print(f"\n💡 Note: Knowledge base scraping must be triggered manually using the 'Build KB' button in the admin panel.")
except Exception as e:
    print(f"\n❌ Error creating business: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
