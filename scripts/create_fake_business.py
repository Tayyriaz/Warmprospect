
import requests
import json

def create_fake_business():
    url = "http://localhost:8000/admin/business"
    
    fake_business = {
        "business_id": "nexus-tech-solutions",
        "business_name": "Nexus Tech Solutions",
        "system_prompt": "You are the AI assistant for Nexus Tech Solutions, a leading provider of cloud computing and cybersecurity services. You help customers learn about our cloud migration, security audits, and managed IT services. Your tone is futuristic, efficient, and highly knowledgeable. When asked about pricing, mention that we provide custom quotes based on infrastructure needs.",
        "primary_goal": "Schedule discovery calls for IT infrastructure audits",
        "personality": "Futuristic, efficient, and professional",
        "greeting_message": "Welcome to the future of IT. How can Nexus Tech Solutions accelerate your digital transformation today?",
        "appointment_link": "https://calendly.com/nexus-tech/discovery",
        "theme_color": "#0f172a",
        "widget_position": "bottom-right",
        "primary_ctas": [
            {"label": "Cloud Migration", "action": "send"},
            {"label": "Security Audit", "action": "send"},
            {"label": "Talk to an Expert", "action": "send"}
        ]
    }
    
    try:
        response = requests.post(url, json=fake_business)
        if response.status_code == 200:
            print("Successfully created fake business: Nexus Tech Solutions")
            print(f"Test URL: http://localhost:8000/?business_id={fake_business['business_id']}")
        else:
            print(f"Failed to create business: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_fake_business()
