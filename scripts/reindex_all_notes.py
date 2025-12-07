"""
Script to re-index all completed notes in ChromaDB for RAG chat
Run this after fix_existing_notes_html.py to sync embeddings with updated content
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db.models import Note, NoteStatus
from app.services.vector_service import index_note, get_notebook_stats
from app.core.config import settings


def reindex_all_notes():
    """
    Re-index all completed notes in ChromaDB
    """
    print("=" * 80)
    print("Starting re-indexing of all notes for RAG chat")
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
        print(f"Found {total_notes} completed notes to index")
        print("=" * 80)

        indexed_count = 0
        error_count = 0
        total_chunks = 0

        for i, note in enumerate(notes, 1):
            try:
                print(f"\n[{i}/{total_notes}] Indexing note ID: {note.id}")
                print(f"  Title: {note.title[:50]}..." if len(note.title) > 50 else f"  Title: {note.title}")
                print(f"  Notebook ID: {note.notebook_id}")

                # Get content (prefer user_edited_text, fallback to gemini_output_text)
                content = note.user_edited_text or note.gemini_output_text

                if not content:
                    print(f"  Skipping: No content")
                    continue

                # Index the note
                chunks = index_note(
                    notebook_id=note.notebook_id,
                    note_id=note.id,
                    title=note.title,
                    html_content=content
                )

                indexed_count += 1
                total_chunks += chunks
                print(f"  Indexed {chunks} chunks")

            except Exception as e:
                error_count += 1
                print(f"  Error: {str(e)}")
                continue

        print("\n" + "=" * 80)
        print("Re-indexing completed!")
        print("=" * 80)
        print(f"Total notes: {total_notes}")
        print(f"Successfully indexed: {indexed_count}")
        print(f"Total chunks created: {total_chunks}")
        print(f"Errors: {error_count}")
        print(f"Skipped: {total_notes - indexed_count - error_count}")
        print("=" * 80)


if __name__ == "__main__":
    try:
        reindex_all_notes()
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
