import sys
import os

# Add parent directory to path so we can import business_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import load_dotenv from main directory context if needed, or rely on business_config's internal loading
from dotenv import load_dotenv
load_dotenv()

from business_config import config_manager

print("Creating default demo-business...")
try:
    config_manager.create_or_update_business(
        business_id="demo-business",
        business_name="GoAccel Demo",
        system_prompt="You are a helpful AI assistant for GoAccel. You help users understand our services.",
        greeting_message="Hi! I'm the GoAccel Demo Bot. Ask me anything!"
    )
    print("Done.")
except Exception as e:
    print(f"Error creating business: {e}")