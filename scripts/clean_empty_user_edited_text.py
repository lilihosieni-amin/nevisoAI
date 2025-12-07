#!/usr/bin/env python3
"""
Clean empty or meaningless user_edited_text from notes
This happens when frontend sends empty editor content (like <p><br></p>)
"""
import sys
import os
import re

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SyncSessionLocal
from app.db.models import Note
from sqlalchemy import select


def has_meaningful_content(html: str) -> bool:
    """Check if HTML has meaningful content beyond whitespace and empty tags"""
    if not html:
        return False

    # Remove all HTML tags
    text_only = re.sub(r'<[^>]+>', '', html)
    text_only = text_only.strip()

    # Check if there's actual text
    return len(text_only) > 0


def main():
    db = SyncSessionLocal()

    try:
        print("=" * 80)
        print("Cleaning empty user_edited_text from notes")
        print("=" * 80)

        # Get all notes with user_edited_text
        notes = db.execute(
            select(Note).where(Note.user_edited_text.isnot(None))
        ).scalars().all()

        print(f"\nFound {len(notes)} notes with user_edited_text")

        cleaned_count = 0
        for note in notes:
            if not has_meaningful_content(note.user_edited_text):
                print(f"\nNote {note.id}: '{note.title}'")
                print(f"  user_edited_text: {note.user_edited_text[:100]}...")
                print(f"  gemini_output_text length: {len(note.gemini_output_text or '')} chars")
                print(f"  → Clearing empty user_edited_text")

                note.user_edited_text = None
                cleaned_count += 1

        if cleaned_count > 0:
            db.commit()
            print("\n" + "=" * 80)
            print(f"✓ Cleaned {cleaned_count} note(s)")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print("No notes needed cleaning")
            print("=" * 80)

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        db.rollback()
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
