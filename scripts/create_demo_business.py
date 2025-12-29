import sys
import os

# Add parent directory to path so we can import business_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import load_dotenv from main directory context if needed, or rely on business_config's internal loading
from dotenv import load_dotenv
load_dotenv()

from business_config import config_manager, DEFAULT_PRIMARY_CTAS, DEFAULT_SECONDARY_CTAS

print("Creating default demo-business...")
try:
    config_manager.create_or_update_business(
        business_id="demo-business",
        business_name="WarmProspect Demo",
        system_prompt="You are a helpful AI assistant for WarmProspect. You help users understand our services.",
        greeting_message="Hi! I'm the WarmProspect Demo Bot. Ask me anything!",
        primary_ctas=DEFAULT_PRIMARY_CTAS,
        secondary_ctas=DEFAULT_SECONDARY_CTAS
    )
    print("Done.")
except Exception as e:
    print(f"Error creating business: {e}")