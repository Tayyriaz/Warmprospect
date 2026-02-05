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
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='business_logo';
        """))
        logo_col = result.fetchone()
        if not logo_col:
            print("Adding business_logo column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN business_logo TEXT"))
            print("✅ business_logo added.")
        else:
            # Check if it's VARCHAR(500) and needs to be changed to TEXT
            if logo_col[1] == 'character varying' and logo_col[2] == 500:
                print("Updating business_logo column from VARCHAR(500) to TEXT...")
                conn.execute(text("ALTER TABLE business_configs ALTER COLUMN business_logo TYPE TEXT"))
                print("✅ business_logo updated to TEXT.")
            else:
                print("✓ business_logo already exists with correct type.")

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

        # Check for categories
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='categories';
        """))
        if not result.fetchone():
            print("Adding categories column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN categories TEXT"))
            print("✅ categories added.")
        else:
            print("✓ categories already exists.")

        # Check for cta_tree
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='cta_tree';
        """))
        if not result.fetchone():
            print("Adding cta_tree column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN cta_tree TEXT"))
            print("✅ cta_tree added.")
        else:
            print("✓ cta_tree already exists.")

        # Check for scraping_status table
        scraping_status_exists = "scraping_status" in inspector.get_table_names()
        if not scraping_status_exists:
            print("Creating scraping_status table...")
            conn.execute(text("""
                CREATE TABLE scraping_status (
                    id SERIAL PRIMARY KEY,
                    business_id VARCHAR(255) NOT NULL UNIQUE,
                    status VARCHAR(50) NOT NULL,
                    message TEXT DEFAULT '',
                    progress INTEGER DEFAULT 0,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_business_id FOREIGN KEY (business_id) REFERENCES business_configs(business_id) ON DELETE CASCADE
                )
            """))
            conn.execute(text("CREATE INDEX idx_scraping_status_business_id ON scraping_status(business_id)"))
            print("✅ scraping_status table created.")
        else:
            print("✓ scraping_status table already exists.")

        print("✅ Migration complete.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
