"""
Enhanced Celery Tasks with Credit Management and Queue Processing
"""
from app.worker.celery_app import celery_app
from app.db.session import SyncSessionLocal
from app.db.models import (
    NoteStatus, Note, Notification, NotificationType,
    QueueStatus, ProcessingQueue
)
from app.worker.error_handler import ProcessingError
from sqlalchemy import select
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


def run_async(coro):
    """Helper to run async code in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(coro)
        # Give pending tasks a chance to finish
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        return result
    finally:
        loop.close()


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
    6. Update queue status
    """
    from app.services.credit_service import credit_manager, InsufficientCreditsError
    from app.services.queue_service import queue_manager

    db = SyncSessionLocal()

    # Main async function that handles all async operations
    async def process_async():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from app.core.config import settings

        # Create async engine and session
        async_engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
        AsyncSessionLocal = sessionmaker(
            async_engine, class_=AsyncSession, expire_on_commit=False
        )

        async with AsyncSessionLocal() as async_db:
            return await process_with_db(async_db, async_engine)

    async def process_with_db(async_db, async_engine):
        """All async operations in one function"""
        logger.info("=" * 80)
        logger.info(f"[WORKER] Starting processing for note {note_id} with credit management")
        logger.info("=" * 80)

        # Get note
        note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
        if not note:
            logger.error(f"[WORKER] Note {note_id} not found")
            return

        user_id = note.user_id

        # Step 1: Calculate required credits
        logger.info(f"[WORKER] Calculating required credits for note {note_id}")

        async def calc_credits():
            async with AsyncSessionLocal() as async_db:
                return await credit_manager.calculate_note_credits(async_db, note_id)

        try:
            required_credits = run_async(calc_credits())
            logger.info(f"[WORKER] Required credits: {required_credits:.2f} minutes")
        except Exception as e:
            logger.error(f"[WORKER] Failed to calculate credits: {str(e)}")
            note.status = NoteStatus.failed
            note.error_message = "خطا در محاسبه اعتبار"
            note.error_detail = str(e)
            db.commit()

            # Update queue
            async def mark_failed():
                async with AsyncSessionLocal() as async_db:
                    await queue_manager.mark_completed(async_db, note_id, False, str(e))
            run_async(mark_failed())
            return

        # Step 2 & 3: Check balance and deduct credits
        logger.info(f"[WORKER] Deducting {required_credits:.2f} minutes from user {user_id}")

        async def deduct():
            async with AsyncSessionLocal() as async_db:
                return await credit_manager.deduct_credits(
                    async_db,
                    user_id,
                    required_credits,
                    note_id=note_id,
                    description=f"پردازش یادداشت: {note.title}"
                )

        try:
            run_async(deduct())
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

            # Update queue
            async def mark_failed():
                async with AsyncSessionLocal() as async_db:
                    await queue_manager.mark_completed(async_db, note_id, False, str(e))
            run_async(mark_failed())
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
            gemini_output = run_async(process_files_with_gemini(file_paths))

            # Update note with results
            title = gemini_output.get('title', note.title)
            note_html = gemini_output.get('note', '')

            note.title = title
            note.gemini_output_text = note_html
            note.status = NoteStatus.completed
            db.commit()

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

            # Update queue
            async def mark_success():
                async with AsyncSessionLocal() as async_db:
                    await queue_manager.mark_completed(async_db, note_id, True)
            run_async(mark_success())

            logger.info("=" * 80)
            logger.info(f"[WORKER] Successfully completed note {note_id}")
            logger.info("=" * 80)

        except Exception as processing_error:
            logger.error("=" * 80)
            logger.error(f"[WORKER] Processing failed for note {note_id}")
            logger.error(f"[WORKER] Error: {str(processing_error)}")
            logger.error("=" * 80)

            # Step 5: Refund credits on error
            logger.info(f"[WORKER] Refunding {required_credits:.2f} minutes to user {user_id}")

            async def refund():
                async with AsyncSessionLocal() as async_db:
                    await credit_manager.refund_credits(
                        async_db,
                        user_id,
                        required_credits,
                        note_id=note_id,
                        description=f"بازگشت اعتبار به دلیل خطا: {note.title}"
                    )

            try:
                run_async(refund())
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

                # Retry via queue
                async def retry_task():
                    async with AsyncSessionLocal() as async_db:
                        await queue_manager.retry_task(async_db, note_id, retry_delay)
                run_async(retry_task())

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

                # Update queue
                async def mark_failed():
                    async with AsyncSessionLocal() as async_db:
                        await queue_manager.mark_completed(
                            async_db, note_id, False, user_message
                        )
                run_async(mark_failed())

    except Exception as fatal_error:
        logger.error("=" * 80)
        logger.error(f"[WORKER] FATAL ERROR processing note {note_id}")
        logger.error(f"[WORKER] Error: {str(fatal_error)}")
        logger.error("=" * 80)

        try:
            note = db.execute(select(Note).where(Note.id == note_id)).scalar_one_or_none()
            if note:
                note.status = NoteStatus.failed
                note.error_message = "خطای سیستمی"
                note.error_detail = str(fatal_error)
                db.commit()
        except Exception as update_error:
            logger.error(f"[WORKER] Failed to update note status: {str(update_error)}")

    finally:
        db.close()


@celery_app.task(name="process_queue")
def process_queue():
    """
    Periodic task to process items from queue

    Runs every 10 seconds (configured in celery beat)
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.services.queue_service import queue_manager

    # Create async session
    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def process():
        async with AsyncSessionLocal() as db:
            # Get next task
            task = await queue_manager.get_next_task(db)

            if task:
                note_id = task['note_id']
                logger.info(f"[QUEUE] Starting processing for note {note_id}")

                # Trigger processing task
                process_file_with_credits.delay(note_id)
            else:
                logger.debug("[QUEUE] No tasks available or at capacity")

    run_async(process())


@celery_app.task(name="cleanup_expired_subscriptions")
def cleanup_expired_subscriptions():
    """
    Daily task to cleanup expired subscriptions and send notifications
    """
    from app.db.models import UserSubscription, SubscriptionStatus
    from datetime import datetime, timedelta

    db = SyncSessionLocal()

    try:
        logger.info("[CLEANUP] Starting subscription cleanup")

        # Find expired subscriptions
        now = datetime.utcnow()
        result = db.execute(
            select(UserSubscription).where(
                UserSubscription.status == SubscriptionStatus.active,
                UserSubscription.end_date < now
            )
        )
        expired = result.scalars().all()

        for sub in expired:
            logger.info(f"[CLEANUP] Expiring subscription {sub.id} for user {sub.user_id}")
            sub.status = SubscriptionStatus.expired

            # Create notification
            notification = Notification(
                user_id=sub.user_id,
                type=NotificationType.subscription_expiring,
                title="اشتراک منقضی شد",
                message=f"اشتراک {sub.plan.name} شما به پایان رسید. برای ادامه استفاده، اشتراک خود را تمدید کنید."
            )
            db.add(notification)

        db.commit()
        logger.info(f"[CLEANUP] Expired {len(expired)} subscriptions")

        # Find subscriptions expiring soon (in 3 days)
        soon = now + timedelta(days=3)
        result = db.execute(
            select(UserSubscription).where(
                UserSubscription.status == SubscriptionStatus.active,
                UserSubscription.end_date > now,
                UserSubscription.end_date < soon
            )
        )
        expiring_soon = result.scalars().all()

        for sub in expiring_soon:
            # Check if we already sent notification
            existing = db.execute(
                select(Notification).where(
                    Notification.user_id == sub.user_id,
                    Notification.type == NotificationType.subscription_expiring,
                    Notification.created_at > now - timedelta(days=1)
                )
            ).scalar_one_or_none()

            if not existing:
                notification = Notification(
                    user_id=sub.user_id,
                    type=NotificationType.subscription_expiring,
                    title="اشتراک رو به پایان است",
                    message=f"اشتراک {sub.plan.name} شما در {sub.end_date.date()} به پایان می‌رسد."
                )
                db.add(notification)

        db.commit()
        logger.info(f"[CLEANUP] Notified {len(expiring_soon)} users about expiring subscriptions")

    except Exception as e:
        logger.error(f"[CLEANUP] Error: {str(e)}", exc_info=True)
        db.rollback()
    finally:
        db.close()


@celery_app.task(name="cleanup_stale_queue_tasks")
def cleanup_stale_queue_tasks():
    """
    Periodic task to clean up stale queue items
    Runs every hour
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.services.queue_service import queue_manager

    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def cleanup():
        async with AsyncSessionLocal() as db:
            await queue_manager.cleanup_stale_tasks(db, timeout_minutes=30)
            logger.info("[CLEANUP] Stale queue tasks cleanup completed")

    run_async(cleanup())


@celery_app.task(name="system_health_check")
def system_health_check():
    """
    Periodic task to check system health and send alerts
    Runs every 5 minutes
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.core.config import settings
    from app.services.monitoring_service import monitoring_service

    async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def check():
        async with AsyncSessionLocal() as db:
            health = await monitoring_service.get_system_health(db)

            if not health.get('healthy'):
                logger.warning("[HEALTH] System health issues detected")
                await monitoring_service.send_alert(
                    "System health issues detected",
                    severity='warning',
                    details=health
                )
            else:
                logger.info("[HEALTH] System healthy")

    run_async(check())
