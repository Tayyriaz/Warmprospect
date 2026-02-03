"""
Database schema synchronization - auto-syncs models with database.
"""

from sqlalchemy import inspect as sqlalchemy_inspect, text
from .connection import engine
from .models import BusinessConfig, Base


def init_db():
    """Initialize database - create all tables."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False


def sync_schema():
    """
    Automatically sync database schema with SQLAlchemy models.
    Compares model definitions with actual database and adds missing columns.
    Safe to run multiple times - only adds what's missing.
    """
    inspector = sqlalchemy_inspect(engine)
    
    # Check if table exists
    if "business_configs" not in inspector.get_table_names():
        print("Table 'business_configs' does not exist. Creating it...")
        init_db()
        return
    
    # Get model columns
    model_columns = {col.name: col for col in BusinessConfig.__table__.columns}
    
    # Get database columns
    db_columns = {col['name']: col for col in inspector.get_columns("business_configs")}
    
    # Find missing columns
    missing_columns = []
    for col_name, col in model_columns.items():
        if col_name not in db_columns:
            missing_columns.append((col_name, col))
    
    if not missing_columns:
        print("✓ Database schema is up to date.")
        return
    
    # Add missing columns
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for col_name, col in missing_columns:
            try:
                # Build ALTER TABLE statement
                col_type = col.type.compile(engine.dialect)
                nullable_clause = "" if col.nullable else "NOT NULL"
                default_clause = ""
                
                if col.default is not None:
                    if hasattr(col.default, 'arg'):
                        default_value = col.default.arg
                        if isinstance(default_value, bool):
                            default_clause = f"DEFAULT {str(default_value).upper()}"
                        elif isinstance(default_value, str):
                            default_clause = f"DEFAULT '{default_value}'"
                        else:
                            default_clause = f"DEFAULT {default_value}"
                    elif hasattr(col.default, 'is_callable') and col.default.is_callable:
                        default_clause = ""
                
                alter_parts = [f"ALTER TABLE business_configs ADD COLUMN {col_name} {col_type}"]
                if nullable_clause:
                    alter_parts.append(nullable_clause)
                if default_clause:
                    alter_parts.append(default_clause)
                
                alter_sql = " ".join(alter_parts)
                conn.execute(text(alter_sql))
                
                print(f"✅ Added column: {col_name} ({col_type})")
            except Exception as e:
                print(f"⚠️  Failed to add column {col_name}: {e}")
                import traceback
                traceback.print_exc()
    
    print("✅ Schema sync complete.")
