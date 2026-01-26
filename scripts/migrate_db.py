from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/warmprospect_db")
engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        print("Checking for missing columns...")
        
        # Check for voice_enabled
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='voice_enabled';
        """))
        if not result.fetchone():
            print("Adding voice_enabled column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN voice_enabled BOOLEAN DEFAULT FALSE"))
        else:
            print("voice_enabled already exists.")

        # Check for chatbot_button_text
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='chatbot_button_text';
        """))
        if not result.fetchone():
            print("Adding chatbot_button_text column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN chatbot_button_text VARCHAR(255)"))
        else:
            print("chatbot_button_text already exists.")

        # Check for business_logo
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='business_logo';
        """))
        if not result.fetchone():
            print("Adding business_logo column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN business_logo VARCHAR(500)"))
        else:
            print("business_logo already exists.")

        print("Migration complete.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
