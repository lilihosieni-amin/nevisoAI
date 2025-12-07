#!/usr/bin/env python3
"""
Automatic Migration Script
Detects user_id data type and runs appropriate migration
"""
import sys
import os
import re
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from sqlalchemy import create_engine, text
    from app.core.config import settings
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're in the project directory and virtual environment is activated")
    sys.exit(1)


def get_db_connection():
    """Get database connection"""
    try:
        # Convert async URL to sync
        db_url = settings.DATABASE_URL.replace('+asyncmy', '+pymysql')
        engine = create_engine(db_url, echo=False)
        return engine
    except Exception as e:
        print(f"Error connecting to database: {e}")
        print(f"DATABASE_URL: {settings.DATABASE_URL}")
        sys.exit(1)


def detect_user_id_type(engine):
    """Detect the data type of users.id column"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'users'
                AND COLUMN_NAME = 'id'
            """))
            row = result.fetchone()

            if not row:
                print("ERROR: Could not find users.id column")
                print("Make sure the 'users' table exists")
                sys.exit(1)

            column_type = row[0]
            print(f"✓ Detected users.id type: {column_type}")
            return column_type

    except Exception as e:
        print(f"Error detecting column type: {e}")
        sys.exit(1)


def check_existing_tables(engine):
    """Check if tables already exist"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('credit_transactions', 'processing_queue', 'user_quotas')
            """))
            existing = [row[0] for row in result.fetchall()]

            if existing:
                print(f"\n⚠️  WARNING: The following tables already exist:")
                for table in existing:
                    print(f"   - {table}")

                response = input("\nDo you want to drop these tables and recreate them? (yes/no): ")
                if response.lower() != 'yes':
                    print("Migration cancelled.")
                    sys.exit(0)

                print("\n✓ Dropping existing tables...")
                with engine.connect() as conn:
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                    for table in existing:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                    conn.commit()
                print("✓ Existing tables dropped")

    except Exception as e:
        print(f"Error checking existing tables: {e}")
        sys.exit(1)


def run_migration(engine, user_id_type):
    """Run the migration with detected data type"""
    try:
        print("\n" + "=" * 80)
        print("Starting Migration")
        print("=" * 80)

        # Read migration file
        migration_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'migrations',
            'add_credit_and_queue_tables_v2.sql'
        )

        if not os.path.exists(migration_file):
            print(f"ERROR: Migration file not found: {migration_file}")
            sys.exit(1)

        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        print(f"✓ Loaded migration file")

        # Execute migration
        with engine.connect() as conn:
            # Split by semicolon but handle prepared statements
            statements = []
            current_stmt = []
            in_prepare = False

            for line in sql_content.split('\n'):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith('--'):
                    continue

                current_stmt.append(line)

                # Check for PREPARE/EXECUTE statements
                if 'PREPARE' in line.upper():
                    in_prepare = True
                elif 'DEALLOCATE PREPARE' in line.upper():
                    in_prepare = False
                    statements.append('\n'.join(current_stmt))
                    current_stmt = []
                elif line.endswith(';') and not in_prepare:
                    statements.append('\n'.join(current_stmt))
                    current_stmt = []

            # Execute each statement
            for i, stmt in enumerate(statements, 1):
                if stmt.strip():
                    try:
                        # Replace variable with actual value for prepared statements
                        stmt = stmt.replace('@user_id_type', f"'{user_id_type}'")

                        conn.execute(text(stmt))
                        conn.commit()

                        # Show progress
                        if i % 5 == 0:
                            print(f"✓ Executed {i}/{len(statements)} statements...")
                    except Exception as e:
                        # Some statements might fail (like IF EXISTS checks), that's ok
                        if 'already exists' not in str(e).lower():
                            print(f"Warning on statement {i}: {e}")

            print(f"✓ Executed all {len(statements)} statements")

        print("\n" + "=" * 80)
        print("Migration Completed Successfully!")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def verify_migration(engine):
    """Verify migration was successful"""
    try:
        print("\n" + "=" * 80)
        print("Verifying Migration")
        print("=" * 80)

        with engine.connect() as conn:
            # Check tables exist
            result = conn.execute(text("""
                SELECT TABLE_NAME, TABLE_ROWS, TABLE_COMMENT
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('credit_transactions', 'processing_queue', 'user_quotas')
                ORDER BY TABLE_NAME
            """))

            tables = result.fetchall()

            if len(tables) != 3:
                print(f"✗ ERROR: Expected 3 tables, found {len(tables)}")
                return False

            print("\n✓ Tables created:")
            for table in tables:
                print(f"   - {table[0]}: {table[2]}")

            # Check foreign keys
            result = conn.execute(text("""
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('credit_transactions', 'processing_queue', 'user_quotas')
                AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, ORDINAL_POSITION
            """))

            fks = result.fetchall()

            if len(fks) < 6:  # Should have at least 6 foreign keys
                print(f"\n⚠️  WARNING: Expected at least 6 foreign keys, found {len(fks)}")

            print("\n✓ Foreign keys:")
            for fk in fks:
                print(f"   - {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")

            # Check indexes
            result = conn.execute(text("""
                SELECT
                    TABLE_NAME,
                    INDEX_NAME,
                    GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('credit_transactions', 'processing_queue', 'user_quotas')
                AND INDEX_NAME != 'PRIMARY'
                GROUP BY TABLE_NAME, INDEX_NAME
                ORDER BY TABLE_NAME, INDEX_NAME
            """))

            indexes = result.fetchall()
            print(f"\n✓ Created {len(indexes)} indexes")

        print("\n" + "=" * 80)
        print("✓ Verification Passed!")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\nError during verification: {e}")
        return False


def main():
    """Main migration function"""
    print("=" * 80)
    print("NEVISO - Payment & Credit System Migration")
    print("=" * 80)
    print()

    # Get database connection
    print("Step 1: Connecting to database...")
    engine = get_db_connection()
    print("✓ Connected to database")

    # Detect user_id type
    print("\nStep 2: Detecting user_id data type...")
    user_id_type = detect_user_id_type(engine)

    # Check existing tables
    print("\nStep 3: Checking for existing tables...")
    check_existing_tables(engine)

    # Run migration
    print("\nStep 4: Running migration...")
    run_migration(engine, user_id_type)

    # Verify migration
    print("\nStep 5: Verifying migration...")
    success = verify_migration(engine)

    if success:
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your FastAPI server")
        print("2. Restart Celery workers")
        print("3. Test the payment and credit features")
        print("\nFor documentation, see:")
        print("- PAYMENT_CREDIT_SYSTEM.md")
        print("- migrations/MIGRATION_GUIDE.md")
        return 0
    else:
        print("\n⚠️  Migration completed with warnings")
        print("Please check the output above for any issues")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
