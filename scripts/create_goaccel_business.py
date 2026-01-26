#!/usr/bin/env python3
"""Create GoAccel business configuration with all fields filled"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from business_config import config_manager

# GoAccel business configuration
business_config = {
    "business_id": "goaccel-website",
    "business_name": "GoAccel",
    "system_prompt": """GoAccel is an all-in-one growth and operations system built specifically for home services and skilled trade businesses. We combine customer acquisition, automation, CRM, scheduling, and operational systems into a single platform designed to help owners scale predictably and build long-term enterprise value.

Our services include:
- Digital Agency Solutions: Full-service digital agency/lead gen services including websites, paid ads, and conversion tracking
- CRM Software: Customer relationship management, deal pipeline management, business management software
- Marketing Automation: Automated appointment booking, lead nurturing, marketing campaign management
- Business Listing Management: Customer review management, data enhancement, database reactivation

We serve industries including HVAC, plumbing, electrical, window cleaning, appliance repair, carpet cleaning, handyman, cleaning & janitorial, garage door, lawn care, pest control, custom home building, pool & spa service, fireplace & chimney, custom remodeling, locksmith, landscaping, painting contractors, junk removal, property maintenance, roofing, and mechanic services.

Your role is to help potential customers understand how GoAccel can help their home services business grow. Be friendly, knowledgeable, and focus on how we can help them achieve predictable growth and build business value.""",
    "primary_goal": "Help home services businesses scale predictably and build long-term enterprise value",
    "personality": "Friendly, knowledgeable, and growth-focused",
    "greeting_message": "Hi! Welcome to GoAccel. I'm here to help you understand how we can accelerate your home services business growth. What would you like to know?",
    "appointment_link": "https://warmprospect.com/goaccel-website/",
    "privacy_statement": "We collect your information only to provide better service and connect you with the right solutions for your business. Your data is secure and will not be shared with third parties.",
    "website_url": "https://warmprospect.com/goaccel-website/",
    "contact_email": "info@goaccel.com",
    "contact_phone": "855.915.0747",
    "theme_color": "#667eea",
    "widget_position": "center"
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
    print(f"\n📝 Next steps:")
    print(f"  1. Backend server restart karein (if needed)")
    print(f"  2. Admin page mein check karein: http://localhost:8000/admin")
    print(f"  3. Test chatbot: http://localhost:8000/?business_id=goaccel-website")
    print(f"\n⚠️ Note: Website URL set hai, toh scraping automatically start hogi jab admin page se save karein.")
except Exception as e:
    print(f"\n❌ Error creating business: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
