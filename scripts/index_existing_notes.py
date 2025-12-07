#!/usr/bin/env python3
"""
Script to index all existing completed notes for RAG chat.
Run this once after adding the chat feature to index old notes.

Usage:
    python scripts/index_existing_notes.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SyncSessionLocal
from app.db.models import Note, NoteStatus
from app.services.vector_service import index_note
from sqlalchemy import select


def index_all_existing_notes():
    """Index all completed notes that have content"""
    db = SyncSessionLocal()

    try:
        # Get all completed, active notes
        result = db.execute(
            select(Note).where(
                Note.status == NoteStatus.completed,
                Note.is_active == True
            )
        )
        notes = result.scalars().all()

        print(f"Found {len(notes)} completed notes to index")

        indexed_count = 0
        error_count = 0

        for note in notes:
            content = note.user_edited_text or note.gemini_output_text
            if not content:
                print(f"  Skipping note {note.id} - no content")
                continue

            try:
                chunks = index_note(
                    notebook_id=note.notebook_id,
                    note_id=note.id,
                    title=note.title,
                    html_content=content
                )
                indexed_count += 1
                print(f"  ✓ Indexed note {note.id}: '{note.title[:50]}...' ({chunks} chunks)")
            except Exception as e:
                error_count += 1
                print(f"  ✗ Failed to index note {note.id}: {e}")

        print("\n" + "=" * 50)
        print(f"Indexing complete!")
        print(f"  Indexed: {indexed_count} notes")
        print(f"  Errors: {error_count} notes")
        print("=" * 50)

    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("Indexing existing notes for RAG chat...")
    print("=" * 50 + "\n")
    index_all_existing_notes()
