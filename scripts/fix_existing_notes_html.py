"""
Script to fix HTML formatting in existing notes
Fixes horizontal scroll issues in code blocks and tables
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db.models import Note, NoteStatus
from app.services.html_processor import html_processor
from app.core.config import settings


def fix_existing_notes():
    """
    Process all existing completed notes to fix HTML formatting
    """
    print("=" * 80)
    print("Starting HTML fix for existing notes")
    print("=" * 80)

    # Create sync engine
    sync_db_url = settings.DATABASE_URL.replace('+asyncmy', '+pymysql')
    engine = create_engine(sync_db_url, echo=False)

    with Session(engine) as session:
        # Get all completed notes
        result = session.execute(
            select(Note).where(Note.status == NoteStatus.completed)
        )
        notes = result.scalars().all()

        total_notes = len(notes)
        print(f"Found {total_notes} completed notes to process")
        print("=" * 80)

        processed_count = 0
        error_count = 0

        for i, note in enumerate(notes, 1):
            try:
                print(f"\n[{i}/{total_notes}] Processing note ID: {note.id}")
                print(f"  Title: {note.title}")

                if not note.gemini_output_text:
                    print(f"  ⚠️  Skipping: No content")
                    continue

                original_length = len(note.gemini_output_text)
                print(f"  Original length: {original_length} characters")

                # Process HTML
                processed_html = html_processor.process_gemini_output(
                    note.gemini_output_text
                )

                new_length = len(processed_html)
                print(f"  Processed length: {new_length} characters")

                # Update note
                note.gemini_output_text = processed_html
                session.commit()

                processed_count += 1
                print(f"  ✓ Successfully processed")

            except Exception as e:
                error_count += 1
                print(f"  ✗ Error: {str(e)}")
                session.rollback()
                continue

        print("\n" + "=" * 80)
        print("Processing completed!")
        print("=" * 80)
        print(f"Total notes: {total_notes}")
        print(f"Successfully processed: {processed_count}")
        print(f"Errors: {error_count}")
        print(f"Skipped: {total_notes - processed_count - error_count}")
        print("=" * 80)


if __name__ == "__main__":
    try:
        fix_existing_notes()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
