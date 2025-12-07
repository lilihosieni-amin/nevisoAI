"""
Enhanced Celery Tasks with Credit Management - Fixed async/await issues
"""
from app.worker.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.db.models import (
    NoteStatus, Note, Notification, NotificationType
)
from app.worker.error_handler import ProcessingError
from sqlalchemy import select
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="process_file_with_credits")
def process_file_with_credits(note_id: int):
    """
    Process file with complete credit management

    Workflow:
    1. Calculate required credits
    2. Check sufficient balance
    3. Deduct credits
    4. Process file
    5. On error: refund credits
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.services.credit_service import credit_manager, InsufficientCreditsError

    db = SyncSessionLocal()

    async def run_processing():
        """Main async processing function"""
        # Create async engine
        async_engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
        AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

        try:
            logger.info("=" * 80)
            logger.info(f"[WORKER] Starting processing for note {note_id} with credit management")
            logger.info("=" * 80)

            # Get note from sync session
            note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
            if not note:
                logger.error(f"[WORKER] Note {note_id} not found")
                return

            user_id = note.user_id

            # Step 1: Calculate required credits
            logger.info(f"[WORKER] Calculating required credits for note {note_id}")

            async with AsyncSessionLocal() as async_db:
                try:
                    required_credits = await credit_manager.calculate_note_credits(async_db, note_id)
                    logger.info(f"[WORKER] Required credits: {required_credits:.2f} minutes")
                except Exception as e:
                    logger.error(f"[WORKER] Failed to calculate credits: {str(e)}")
                    note.status = NoteStatus.failed
                    note.error_message = "خطا در محاسبه اعتبار"
                    note.error_detail = str(e)
                    db.commit()
                    return

            # Step 2 & 3: Check balance and deduct credits
            logger.info(f"[WORKER] Deducting {required_credits:.2f} minutes from user {user_id}")

            async with AsyncSessionLocal() as async_db:
                try:
                    await credit_manager.deduct_credits(
                        async_db,
                        user_id,
                        required_credits,
                        note_id=note_id,
                        description=f"پردازش یادداشت: {note.title}"
                    )
                    logger.info(f"[WORKER] Credits deducted successfully")
                except InsufficientCreditsError as e:
                    logger.error(f"[WORKER] Insufficient credits: {str(e)}")
                    note.status = NoteStatus.failed
                    note.error_message = "اعتبار کافی نیست"
                    note.error_detail = str(e)
                    db.commit()

                    # Create notification
                    notification = Notification(
                        user_id=user_id,
                        type=NotificationType.quota_warning,
                        title="اعتبار ناکافی",
                        message=f"برای پردازش '{note.title}' اعتبار کافی ندارید. لطفا اشتراک خود را تمدید کنید.",
                        related_note_id=note_id
                    )
                    db.add(notification)
                    db.commit()
                    return

            # Step 4: Process with Gemini AI
            logger.info(f"[WORKER] Processing with Gemini AI...")

            try:
                from app.db.models import Upload
                from app.services.ai_service import process_files_with_gemini

                # Get uploads
                uploads = db.execute(select(Upload).where(Upload.note_id == note_id)).scalars().all()
                if not uploads:
                    raise Exception("No uploads found")

                file_paths = [upload.storage_path for upload in uploads]
                logger.info(f"[WORKER] Processing {len(file_paths)} file(s)")

                # Process with Gemini
                gemini_output = await process_files_with_gemini(file_paths)

                # Update note with results
                title = gemini_output.get('title', note.title)
                note_html = gemini_output.get('note', '')

                # Process HTML
                from app.services.html_processor import html_processor
                processed_html = html_processor.process_gemini_output(note_html)

                note.title = title
                note.gemini_output_text = processed_html
                note.user_edited_text = processed_html
                note.status = NoteStatus.completed
                db.commit()

                # Index note content for RAG chat
                try:
                    from app.services.vector_service import index_note as index_note_for_rag
                    chunks_indexed = index_note_for_rag(
                        notebook_id=note.notebook_id,
                        note_id=note.id,
                        title=title,
                        html_content=processed_html
                    )
                    logger.info(f"[WORKER] Indexed {chunks_indexed} chunks for RAG chat")
                except Exception as index_error:
                    # Don't fail the note if indexing fails, just log it
                    logger.warning(f"[WORKER] Failed to index note for RAG: {str(index_error)}")

                # Create success notification
                notification = Notification(
                    user_id=user_id,
                    type=NotificationType.note_completed,
                    title="یادداشت آماده است",
                    message=f"یادداشت '{note.title}' با موفقیت پردازش شد",
                    related_note_id=note_id
                )
                db.add(notification)
                db.commit()

                logger.info("=" * 80)
                logger.info(f"[WORKER] Successfully completed note {note_id}")
                logger.info("=" * 80)

            except Exception as processing_error:
                logger.error("=" * 80)
                logger.error(f"[WORKER] Processing failed for note {note_id}")
                logger.error(f"[WORKER] Error: {str(processing_error)}")
                logger.error("=" * 80)

                # Rollback any pending transaction to clear the session state
                db.rollback()

                # Re-fetch the note to ensure clean state
                note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
                if not note:
                    logger.error(f"[WORKER] Note {note_id} not found after rollback")
                    return

                # Step 5: Refund credits on error
                logger.info(f"[WORKER] Refunding {required_credits:.2f} minutes to user {user_id}")

                async with AsyncSessionLocal() as async_db:
                    try:
                        await credit_manager.refund_credits(
                            async_db,
                            user_id,
                            required_credits,
                            note_id=note_id,
                            description=f"بازگشت اعتبار به دلیل خطا: {note.title}"
                        )
                        logger.info(f"[WORKER] Credits refunded successfully")
                    except Exception as refund_error:
                        logger.error(f"[WORKER] Failed to refund credits: {str(refund_error)}")

                # Handle retry logic
                category, user_message, error_detail, retryable = ProcessingError.classify_error(
                    processing_error
                )
                current_retry = note.retry_count or 0

                should_retry = ProcessingError.should_retry(
                    processing_error, current_retry, max_retries=3
                )

                if should_retry:
                    retry_delay = ProcessingError.get_retry_delay(current_retry)
                    logger.info(f"[WORKER] Scheduling retry in {retry_delay} seconds")

                    note.retry_count = current_retry + 1
                    note.error_message = user_message
                    note.error_detail = error_detail
                    note.last_error_at = datetime.now()
                    note.status = NoteStatus.processing
                    db.commit()

                    # Schedule retry
                    process_file_with_credits.apply_async((note_id,), countdown=retry_delay)

                else:
                    logger.info(f"[WORKER] Max retries reached. Marking as failed.")

                    note.status = NoteStatus.failed
                    note.error_message = user_message
                    note.error_detail = error_detail
                    note.error_type = category
                    note.last_error_at = datetime.now()
                    db.commit()

                    # Create failure notification
                    notification = Notification(
                        user_id=user_id,
                        type=NotificationType.note_failed,
                        title="خطا در پردازش",
                        message=f"یادداشت '{note.title}' با خطا مواجه شد: {user_message}",
                        related_note_id=note_id
                    )
                    db.add(notification)
                    db.commit()

        finally:
            await async_engine.dispose()

    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_processing())
    finally:
        # Cancel any pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Wait for all tasks to finish cancellation
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        db.close()
