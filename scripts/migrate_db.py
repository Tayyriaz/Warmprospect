from sqlalchemy import create_engine, text, inspect
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/warmprospect_db")
# Force synchronous psycopg2 driver for migrations
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
engine = create_engine(DATABASE_URL)

def migrate():
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        
        # Check if table exists
        inspector = inspect(engine)
        table_exists = "business_configs" in inspector.get_table_names()
        
        if not table_exists:
            print("Table 'business_configs' does not exist. Creating it first...")
            try:
                from core.database import init_db
                init_db()
                print("✅ Table created successfully!")
            except Exception as e:
                print(f"❌ Failed to create table: {e}")
                import traceback
                traceback.print_exc()
                raise
        
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
            print("✅ voice_enabled added.")
        else:
            print("✓ voice_enabled already exists.")

        # Check for chatbot_button_text
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='chatbot_button_text';
        """))
        if not result.fetchone():
            print("Adding chatbot_button_text column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN chatbot_button_text VARCHAR(255)"))
            print("✅ chatbot_button_text added.")
        else:
            print("✓ chatbot_button_text already exists.")

        # Check for business_logo
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='business_logo';
        """))
        if not result.fetchone():
            print("Adding business_logo column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN business_logo VARCHAR(500)"))
            print("✅ business_logo added.")
        else:
            print("✓ business_logo already exists.")

        # Check for enabled_categories
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='enabled_categories';
        """))
        if not result.fetchone():
            print("Adding enabled_categories column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN enabled_categories TEXT"))
            print("✅ enabled_categories added.")
        else:
            print("✓ enabled_categories already exists.")

        print("✅ Migration complete.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
