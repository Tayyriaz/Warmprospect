#!/usr/bin/env python3
"""Create Sidhya Asia business configuration with all fields filled"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from business_config import config_manager

# Sidhya Asia business configuration
business_config = {
    "business_id": "sidhya-asia",
    "business_name": "Sidhya Asia Chemical Private Limited",
    "system_prompt": """Sidhya Asia Chemical Private Limited is an Indian company specializing in innovative concrete solutions and construction chemicals. Established in July 2022 and headquartered in Chennai, Tamil Nadu, the company focuses on enhancing construction quality and efficiency through its advanced product offerings.

COMPANY OVERVIEW:
- Established: July 2022
- Headquarters: Chennai, Tamil Nadu, India
- Specialization: Innovative concrete solutions and construction chemicals
- Mission: Enhancing construction quality and efficiency

OUR PRODUCT SOLUTIONS:

1. CONCRETE SOLUTIONS:
   - Sidhya® Colors: Concrete coloring solutions
   - Sidhya® Crete: High-performance concrete admixtures
   - Sidhya® Crete RD: Ready-mix concrete solutions
   - Sidhya® Fibre: Fiber reinforcement for concrete
   - Sidhya® Flow: Flowable concrete solutions
   - Sidhya® Microsil: Microsilica-based solutions
   - Sidhya® Plast: Plasticizers for concrete
   - Sidhya® Protect: Concrete protection systems
   - Sidhya® Quickset: Quick-setting concrete solutions
   - Value Added Products: Additional concrete enhancement products

2. PRECAST SOLUTIONS:
   - Sidhya® Colors: For precast coloring
   - Sidhya® Crete: Precast concrete admixtures
   - Sidhya® Microsil: Microsilica for precast
   - Sidhya® Protect: Protection for precast elements
   - Sidhya® Quickset: Quick-setting for precast
   - Sidhya® Release Aid: Mould release agents
   - Sidhya® Shutter Aid: Shuttering solutions
   - Sidhya® Visco: Viscosity modifiers
   - Value Added Products: Additional precast solutions

3. TUNNEL SOLUTIONS:
   - Sidhya® Grout Fluid: Grouting solutions for tunnels
   - Sidhya® Roc Drive: Rock stabilization solutions
   - Sidhya® Bentocrete: Bentonite-based concrete
   - Sidhya® Soil Plast: Soil plasticization
   - Sidhya® Visco: Viscosity control
   - Sidhya® Fibre: Fiber reinforcement
   - Sidhya® Quick Crete: Fast-setting tunnel concrete
   - Sidhya® Quick Set AGG: Quick-setting aggregates

4. INTERLOCK AND TILES SOLUTIONS:
   - Sidhya® Plast SD: Plasticizers for interlock/tiles
   - Sidhya® Microsil: Microsilica solutions
   - Sidhya® Sealcoat: Sealing solutions
   - Sidhya® Mould Aid: Moulding assistance
   - Sidhya® Colors: Coloring for tiles/interlocks
   - Sidhya® Cleantech: Cleaning technology
   - Value Added Products: Additional solutions

QUALITY CERTIFICATIONS:
- ISO Certification: International quality standards
- NABL Certification: National Accreditation Board for Testing and Calibration Laboratories

SUSTAINABILITY:
We are committed to sustainable products and efficient use of concrete. Many of our products contribute to sustainable construction practices.

COMPANY MEANING:
Sidhya (सिध्य) means 'auspicious'. We infuse auspiciousness into your concrete through our products. The yellow in our logo symbolizes this essence.

Your role is to help potential customers understand how Sidhya Asia's products can enhance their construction projects. Be professional, knowledgeable about construction chemicals, and focus on quality, durability, and efficiency. Help customers choose the right products for their specific construction needs.""",
    
    "primary_goal": "Provide innovative concrete solutions and construction chemicals to enhance construction quality and efficiency",
    "personality": "Professional, knowledgeable, and solution-focused",
    "greeting_message": "Hello! Welcome to Sidhya Asia Chemical. I'm here to help you find the right concrete solutions and construction chemicals for your project. How can I assist you today?",
    "appointment_link": "https://sidhyaasia.com/contact-us",
    "privacy_statement": "We collect your information only to provide better service and connect you with the right solutions for your construction needs. Your data is secure and will not be shared with third parties.",
    "website_url": "https://sidhyaasia.com/",
    "contact_email": "info@sidhyaasia.com",
    "contact_phone": "+91 99 444 798 55",
    "theme_color": "#FFA500",  # Orange/Yellow theme (matching their brand)
    "widget_position": "center",
    "primary_ctas": [
        {"label": "Request Product Information", "action": "send", "message": "I'd like to know more about your concrete solutions and construction chemicals."},
        {"label": "Get Technical Support", "action": "send", "message": "I need technical support for my construction project."},
        {"label": "View Product Categories", "action": "show_secondary"}
    ],
    "secondary_ctas": [
        {"label": "Concrete Solutions", "action": "send", "message": "Tell me about your concrete solutions products."},
        {"label": "Precast Solutions", "action": "send", "message": "I want to know about your precast solutions."},
        {"label": "Tunnel Solutions", "action": "send", "message": "What tunnel solutions do you offer?"},
        {"label": "Interlock & Tiles Solutions", "action": "send", "message": "Tell me about your interlock and tiles solutions."},
        {"label": "Contact Sales Team", "action": "send", "message": "I'd like to speak with your sales team."},
        {"label": "Quality Certifications", "action": "send", "message": "What quality certifications do you have?"}
    ]
}

print("Creating Sidhya Asia business configuration...")
print(f"Business ID: {business_config['business_id']}")
print(f"Business Name: {business_config['business_name']}")
print(f"Website URL: {business_config['website_url']}")

try:
    config = config_manager.create_or_update_business(**business_config)
    print("\n✅ Sidhya Asia business created successfully!")
    print(f"\nConfiguration saved:")
    print(f"  - Business ID: {config['business_id']}")
    print(f"  - Business Name: {config['business_name']}")
    print(f"  - Website URL: {config.get('website_url', 'N/A')}")
    print(f"  - Contact Email: {config.get('contact_email', 'N/A')}")
    print(f"  - Contact Phone: {config.get('contact_phone', 'N/A')}")
    print(f"  - Theme Color: {config.get('theme_color', 'N/A')}")
    print(f"\n📝 Next steps:")
    print(f"  1. Backend server restart karein (if needed)")
    print(f"  2. Admin page mein check karein: http://localhost:8000/admin")
    print(f"  3. Test chatbot: http://localhost:8000/?business_id=sidhya-asia")
    print(f"\n⚠️ Note: Website URL set hai, toh scraping automatically start hogi jab admin page se save karein.")
    print(f"   Ya manually run karein: python scripts/build_kb_for_business.py --business_id sidhya-asia --url https://sidhyaasia.com/")
except Exception as e:
    print(f"\n❌ Error creating business: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
