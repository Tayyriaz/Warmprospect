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
        
        # Check if columns exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='primary_ctas';
        """))
        
        if not result.fetchone():
            print("Adding primary_ctas column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN primary_ctas TEXT"))
        else:
            print("primary_ctas already exists.")

        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='business_configs' AND column_name='secondary_ctas';
        """))

        if not result.fetchone():
            print("Adding secondary_ctas column...")
            conn.execute(text("ALTER TABLE business_configs ADD COLUMN secondary_ctas TEXT"))
        else:
            print("secondary_ctas already exists.")

        print("Migration complete.")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"Migration failed: {e}")
