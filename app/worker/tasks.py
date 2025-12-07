from app.worker.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.db.models import NoteStatus, Note, Notification, NotificationType
from app.worker.error_handler import ProcessingError
from app.services.exceptions import AIProcessingError
from sqlalchemy import select, func
from sqlalchemy.exc import OperationalError
from datetime import datetime
import asyncio
import time


def commit_with_retry(db, max_retries=3, base_delay=0.1):
    """
    Commit database transaction with automatic retry on deadlock.

    Args:
        db: Database session
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will use exponential backoff)

    Raises:
        OperationalError: If deadlock persists after all retries
    """
    for attempt in range(max_retries):
        try:
            db.commit()
            return  # Success
        except OperationalError as e:
            # Check if it's a deadlock error (MySQL error code 1213)
            if "1213" in str(e) or "Deadlock" in str(e):
                db.rollback()  # Rollback the failed transaction

                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"[WORKER] Deadlock detected, retrying in {delay}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    print(f"[WORKER] ✗ Deadlock persisted after {max_retries} attempts")
                    raise
            else:
                # Not a deadlock error, re-raise immediately
                db.rollback()
                raise


@celery_app.task(name="process_file_task")
def process_file_task(note_id: int):
    """
    Background task to process uploaded files with Gemini AI

    Uses sync database operations but async AI processing

    Args:
        note_id: ID of the note to process
    """
    db = SyncSessionLocal()

    try:
        print("=" * 80)
        print(f"[WORKER] Starting processing for note {note_id}")
        print("=" * 80)

        # Get note by ID without user_id check (for worker)
        print(f"[WORKER] Fetching note {note_id} from database...")
        note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()

        if not note:
            print(f"[WORKER] ✗ ERROR: Note {note_id} not found in database")
            return

        print(f"[WORKER] ✓ Note {note_id} found. Title: {note.title}, Status: {note.status}")

        # Get uploads using sync query
        print(f"[WORKER] Fetching uploads for note {note_id}...")
        from app.db.models import Upload
        uploads = db.execute(select(Upload).where(Upload.note_id == note_id)).scalars().all()

        if not uploads:
            print(f"[WORKER] ✗ ERROR: No uploads found for note {note_id}")
            # Update note status to failed
            note.status = NoteStatus.failed
            commit_with_retry(db)
            return

        print(f"[WORKER] ✓ Found {len(uploads)} upload(s)")

        # Get all file paths
        file_paths = [upload.storage_path for upload in uploads]
        print(f"[WORKER] File paths to process:")
        for i, path in enumerate(file_paths, 1):
            print(f"[WORKER]   {i}. {path}")

        # Process with Gemini AI (this is async, so we need event loop)
        print(f"[WORKER] Calling Gemini AI service...")
        try:
            from app.services.ai_service import process_files_with_gemini

            # Create new event loop for async AI processing
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gemini_output = loop.run_until_complete(process_files_with_gemini(file_paths))
            finally:
                loop.close()

            print(f"[WORKER] ✓ Gemini processing successful for note {note_id}")
            print(f"[WORKER] Gemini output keys: {list(gemini_output.keys())}")

            # Extract title and note from Gemini JSON
            title = gemini_output.get('title', note.title)
            note_html = gemini_output.get('note', '')

            print(f"[WORKER] Extracted title: {title}")
            print(f"[WORKER] Extracted note length: {len(note_html)} characters")

            # Validate HTML completeness
            print(f"[WORKER] Validating HTML completeness...")
            if not note_html or len(note_html.strip()) < 10:
                raise Exception("HTML output is empty or too short")

            # Check for common signs of truncation
            open_tags = note_html.count('<')
            close_tags = note_html.count('>')
            if abs(open_tags - close_tags) > 5:  # Allow small difference
                print(f"[WORKER] ⚠ Warning: HTML might be truncated (< count: {open_tags}, > count: {close_tags})")

            # Check if HTML ends properly (should end with a closing tag)
            if not note_html.strip().endswith('>'):
                print(f"[WORKER] ⚠ Warning: HTML doesn't end with a closing tag")
                print(f"[WORKER] Last 100 chars: {note_html[-100:]}")

            # Process HTML to fix formatting issues (prevent horizontal scroll)
            print(f"[WORKER] Processing HTML to fix code blocks and tables...")
            from app.services.html_processor import html_processor
            processed_html = html_processor.process_gemini_output(note_html)
            print(f"[WORKER] HTML processing completed")
            print(f"[WORKER] Processed HTML length: {len(processed_html)} characters")

            # Update note with results (sync)
            print(f"[WORKER] Updating note {note_id} in database...")
            note.title = title
            note.gemini_output_text = processed_html
            note.status = NoteStatus.completed
            commit_with_retry(db)
            print(f"[WORKER] ✓ Note {note_id} updated successfully")

            # Create success notification
            notification = Notification(
                user_id=note.user_id,
                type=NotificationType.note_completed,
                title="یادداشت آماده است",
                message=f"یادداشت '{note.title}' با موفقیت پردازش شد",
                related_note_id=note_id
            )
            db.add(notification)
            commit_with_retry(db)
            print(f"[WORKER] ✓ Notification created successfully")

            # Index note content for RAG chat
            try:
                from app.services.vector_service import index_note as index_note_for_rag
                chunks_indexed = index_note_for_rag(
                    notebook_id=note.notebook_id,
                    note_id=note.id,
                    title=title,
                    html_content=processed_html
                )
                print(f"[WORKER] ✓ Indexed {chunks_indexed} chunks for RAG chat")
            except Exception as index_error:
                # Don't fail the note if indexing fails, just log it
                print(f"[WORKER] ⚠ Warning: Failed to index note for RAG: {str(index_error)}")

            print("=" * 80)
            print(f"[WORKER] ✓ Note {note_id} processing completed successfully")
            print("=" * 80)

        except Exception as ai_error:
            print("=" * 80)
            print(f"[WORKER] ✗ Gemini processing failed for note {note_id}")
            print(f"[WORKER] Error: {str(ai_error)}")
            print(f"[WORKER] Error type: {type(ai_error).__name__}")
            import traceback
            print(f"[WORKER] Traceback:\n{traceback.format_exc()}")
            print("=" * 80)

            # Rollback any pending transaction before accessing note attributes
            try:
                db.rollback()
            except:
                pass

            # Re-fetch note to ensure clean state
            note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
            if not note:
                print(f"[WORKER] ✗ ERROR: Could not re-fetch note {note_id}")
                return

            # Classify error and determine if we should retry
            category, user_message, error_detail, retryable = ProcessingError.classify_error(ai_error)
            current_retry = note.retry_count or 0

            print(f"[WORKER] Error category: {category}")
            print(f"[WORKER] Retryable: {retryable}")
            print(f"[WORKER] Current retry count: {current_retry}")

            should_retry = ProcessingError.should_retry(ai_error, current_retry, max_retries=3)

            if should_retry:
                retry_delay = ProcessingError.get_retry_delay(current_retry)
                print(f"[WORKER] Will retry in {retry_delay} seconds...")

                # Update note with error info and increment retry count
                note.retry_count = current_retry + 1
                note.error_message = user_message
                note.error_detail = error_detail
                note.last_error_at = datetime.now()
                note.status = NoteStatus.processing  # Keep it in processing for retry
                commit_with_retry(db)

                # Schedule retry
                process_file_task.apply_async((note_id,), countdown=retry_delay)
                print(f"[WORKER] Retry #{note.retry_count} scheduled for note {note_id}")
            else:
                print(f"[WORKER] Max retries reached or error not retryable. Marking as failed.")

                # Update note status to failed with error details
                note.status = NoteStatus.failed
                note.error_message = user_message
                note.error_detail = error_detail
                note.error_type = category
                note.last_error_at = datetime.now()
                commit_with_retry(db)

                # Create notification for failed note
                notification = Notification(
                    user_id=note.user_id,
                    type=NotificationType.note_failed,
                    title="خطا در پردازش یادداشت",
                    message=f"یادداشت '{note.title}' با خطا مواجه شد: {user_message}",
                    related_note_id=note_id
                )
                db.add(notification)
                commit_with_retry(db)
                print(f"[WORKER] Notification created for user {note.user_id}")

    except Exception as e:
        print("=" * 80)
        print(f"[WORKER] ✗ FATAL ERROR processing note {note_id}")
        print(f"[WORKER] Error: {str(e)}")
        print(f"[WORKER] Error type: {type(e).__name__}")
        import traceback
        print(f"[WORKER] Traceback:\n{traceback.format_exc()}")
        print("=" * 80)

        try:
            # Rollback any pending transaction
            db.rollback()

            # Try to update note status to failed
            note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
            if note:
                note.status = NoteStatus.failed
                commit_with_retry(db)
        except Exception as update_error:
            print(f"[WORKER] ✗ Failed to update note status: {str(update_error)}")

    finally:
        # Always close the database session
        db.close()
