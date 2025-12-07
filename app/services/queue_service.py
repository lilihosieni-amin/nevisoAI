"""
Queue Management System with Redis
Handles processing queue with priority, rate limiting, and capacity management
"""
import redis
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ProcessingQueue, QueueStatus, UserQuota,
    UserSubscription, SubscriptionStatus, Note
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class QueueError(Exception):
    """Base exception for queue errors"""
    pass


class RateLimitExceededError(QueueError):
    """Raised when user exceeds rate limit"""
    pass


class QueueCapacityError(QueueError):
    """Raised when queue is at capacity"""
    pass


class QueueManager:
    """
    Manages processing queue with:
    - Priority-based ordering (premium users first)
    - Rate limiting per user
    - Concurrent processing limits
    - Retry mechanism with exponential backoff
    """

    # Redis keys
    QUEUE_KEY = "neviso:processing_queue"
    PROCESSING_KEY = "neviso:processing_count"
    USER_RATE_LIMIT_KEY = "neviso:rate_limit:user:{user_id}"
    USER_DAILY_COUNT_KEY = "neviso:daily_count:user:{user_id}"

    def __init__(self):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            logger.info("QueueManager initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise QueueError(f"Redis connection failed: {str(e)}")

    async def check_user_rate_limit(
        self,
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Check if user has exceeded rate limits

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if within limits

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        try:
            # Check per-minute rate limit using Redis
            rate_limit_key = self.USER_RATE_LIMIT_KEY.format(user_id=user_id)
            current_count = self.redis_client.get(rate_limit_key)

            if current_count and int(current_count) >= settings.MAX_USER_UPLOADS_PER_MINUTE:
                logger.warning(f"User {user_id} exceeded per-minute rate limit")
                raise RateLimitExceededError(
                    f"حداکثر {settings.MAX_USER_UPLOADS_PER_MINUTE} فایل در دقیقه مجاز است. لطفا کمی صبر کنید."
                )

            # Check daily limit from database
            result = await db.execute(
                select(UserQuota).where(UserQuota.user_id == user_id)
            )
            quota = result.scalar_one_or_none()

            if quota:
                # Check if we need to reset daily count
                today = datetime.utcnow().date()
                if quota.last_reset_at < today:
                    # Reset counters
                    quota.daily_upload_count = 0
                    quota.total_minutes_used_today = 0
                    quota.last_reset_at = today
                    await db.commit()

                # Check daily limit
                if quota.daily_upload_count >= settings.MAX_USER_UPLOADS_PER_DAY:
                    logger.warning(f"User {user_id} exceeded daily upload limit")
                    raise RateLimitExceededError(
                        f"حداکثر {settings.MAX_USER_UPLOADS_PER_DAY} فایل در روز مجاز است."
                    )

            return True

        except RateLimitExceededError:
            raise
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}", exc_info=True)
            # Don't block user on error
            return True

    async def increment_user_counters(
        self,
        db: AsyncSession,
        user_id: int
    ):
        """
        Increment user's rate limit counters

        Args:
            db: Database session
            user_id: User ID
        """
        try:
            # Increment Redis counter (1 minute TTL)
            rate_limit_key = self.USER_RATE_LIMIT_KEY.format(user_id=user_id)
            pipe = self.redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, 60)  # 1 minute
            pipe.execute()

            # Increment database counter
            result = await db.execute(
                select(UserQuota).where(UserQuota.user_id == user_id)
            )
            quota = result.scalar_one_or_none()

            if quota:
                quota.daily_upload_count += 1
                quota.last_upload_at = datetime.utcnow()
            else:
                # Create new quota record
                quota = UserQuota(
                    user_id=user_id,
                    daily_upload_count=1,
                    last_upload_at=datetime.utcnow(),
                    last_reset_at=datetime.utcnow().date()
                )
                db.add(quota)

            await db.commit()

        except Exception as e:
            logger.error(f"Error incrementing user counters: {str(e)}", exc_info=True)

    async def get_user_priority(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """
        Get user's priority level based on subscription

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Priority level (0=normal, 1=premium, 2=urgent)
        """
        try:
            # Check if user has any active premium subscription
            result = await db.execute(
                select(UserSubscription)
                .join(UserSubscription.plan)
                .where(
                    and_(
                        UserSubscription.user_id == user_id,
                        UserSubscription.status == SubscriptionStatus.active,
                        UserSubscription.end_date > datetime.utcnow()
                    )
                )
            )
            subscriptions = result.scalars().all()

            if not subscriptions:
                return 0  # Normal priority

            # Premium users get higher priority
            # You can customize this based on plan features
            for sub in subscriptions:
                if hasattr(sub.plan, 'features') and sub.plan.features:
                    if sub.plan.features.get('priority') == 'high':
                        return 2  # Urgent
                    elif sub.plan.features.get('priority') == 'medium':
                        return 1  # Premium

            # Default to premium if they have any active subscription
            return 1

        except Exception as e:
            logger.error(f"Error getting user priority: {str(e)}", exc_info=True)
            return 0

    async def add_to_queue(
        self,
        db: AsyncSession,
        note_id: int,
        user_id: int,
        estimated_credits: Optional[float] = None
    ) -> Dict:
        """
        Add a note to processing queue

        Args:
            db: Database session
            note_id: Note ID
            user_id: User ID
            estimated_credits: Estimated credits required

        Returns:
            Queue entry dict with position and estimated time

        Raises:
            RateLimitExceededError: If rate limit exceeded
            QueueError: If queue operation fails
        """
        try:
            # Check rate limits
            await self.check_user_rate_limit(db, user_id)

            # Get user priority
            priority = await self.get_user_priority(db, user_id)

            # Check if already in queue
            result = await db.execute(
                select(ProcessingQueue).where(ProcessingQueue.note_id == note_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.warning(f"Note {note_id} already in queue")
                return {
                    'queue_id': existing.id,
                    'status': existing.status.value,
                    'priority': existing.priority
                }

            # Create queue entry
            queue_entry = ProcessingQueue(
                note_id=note_id,
                user_id=user_id,
                priority=priority,
                status=QueueStatus.waiting,
                estimated_credits=estimated_credits,
                added_at=datetime.utcnow()
            )
            db.add(queue_entry)
            await db.commit()
            await db.refresh(queue_entry)

            # Add to Redis sorted set (score = priority * 1000000 - timestamp)
            # This ensures high priority items come first, then ordered by time
            score = (priority * 1000000) - int(datetime.utcnow().timestamp())
            self.redis_client.zadd(
                self.QUEUE_KEY,
                {str(note_id): score}
            )

            # Increment user counters
            await self.increment_user_counters(db, user_id)

            # Get queue position
            position = await self.get_queue_position(note_id)

            logger.info(
                f"Added note {note_id} to queue. Priority: {priority}, Position: {position}"
            )

            return {
                'queue_id': queue_entry.id,
                'status': QueueStatus.waiting.value,
                'priority': priority,
                'position': position,
                'estimated_wait_minutes': position * 2  # Rough estimate
            }

        except RateLimitExceededError:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Error adding to queue: {str(e)}", exc_info=True)
            raise QueueError(f"Could not add to queue: {str(e)}")

    async def get_queue_position(self, note_id: int) -> int:
        """
        Get position of note in queue

        Args:
            note_id: Note ID

        Returns:
            Queue position (1-based)
        """
        try:
            rank = self.redis_client.zrevrank(self.QUEUE_KEY, str(note_id))
            if rank is None:
                return -1
            return rank + 1  # Convert to 1-based
        except Exception as e:
            logger.error(f"Error getting queue position: {str(e)}")
            return -1

    async def get_next_task(
        self,
        db: AsyncSession
    ) -> Optional[Dict]:
        """
        Get next task from queue based on priority and capacity

        Args:
            db: Database session

        Returns:
            Task dict or None if no tasks available or at capacity
        """
        try:
            # Check current processing count
            processing_count = int(self.redis_client.get(self.PROCESSING_KEY) or 0)

            if processing_count >= settings.MAX_CONCURRENT_PROCESSING:
                logger.debug(f"At capacity: {processing_count}/{settings.MAX_CONCURRENT_PROCESSING}")
                return None

            # Get highest priority item from Redis
            items = self.redis_client.zrevrange(self.QUEUE_KEY, 0, 0)

            if not items:
                logger.debug("No items in queue")
                return None

            note_id = int(items[0])

            # Get queue entry from database
            result = await db.execute(
                select(ProcessingQueue)
                .where(
                    and_(
                        ProcessingQueue.note_id == note_id,
                        ProcessingQueue.status == QueueStatus.waiting
                    )
                )
            )
            queue_entry = result.scalar_one_or_none()

            if not queue_entry:
                # Remove from Redis if not in DB
                self.redis_client.zrem(self.QUEUE_KEY, str(note_id))
                # Try again recursively
                return await self.get_next_task(db)

            # Update status to processing
            queue_entry.status = QueueStatus.processing
            queue_entry.started_at = datetime.utcnow()
            await db.commit()

            # Remove from Redis queue
            self.redis_client.zrem(self.QUEUE_KEY, str(note_id))

            # Increment processing counter
            self.redis_client.incr(self.PROCESSING_KEY)

            logger.info(f"Got next task: note_id={note_id}, priority={queue_entry.priority}")

            return {
                'note_id': note_id,
                'user_id': queue_entry.user_id,
                'priority': queue_entry.priority,
                'queue_id': queue_entry.id
            }

        except Exception as e:
            logger.error(f"Error getting next task: {str(e)}", exc_info=True)
            return None

    async def mark_completed(
        self,
        db: AsyncSession,
        note_id: int,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        Mark a task as completed or failed

        Args:
            db: Database session
            note_id: Note ID
            success: Whether processing was successful
            error_message: Error message if failed
        """
        try:
            # Get queue entry
            result = await db.execute(
                select(ProcessingQueue).where(ProcessingQueue.note_id == note_id)
            )
            queue_entry = result.scalar_one_or_none()

            if queue_entry:
                queue_entry.status = QueueStatus.completed if success else QueueStatus.failed
                queue_entry.completed_at = datetime.utcnow()
                if error_message:
                    queue_entry.error_message = error_message
                await db.commit()

            # Decrement processing counter
            self.redis_client.decr(self.PROCESSING_KEY)

            # Ensure counter doesn't go negative
            if int(self.redis_client.get(self.PROCESSING_KEY) or 0) < 0:
                self.redis_client.set(self.PROCESSING_KEY, 0)

            logger.info(f"Marked note {note_id} as {'completed' if success else 'failed'}")

        except Exception as e:
            logger.error(f"Error marking completed: {str(e)}", exc_info=True)

    async def retry_task(
        self,
        db: AsyncSession,
        note_id: int,
        delay_seconds: int = 60
    ):
        """
        Retry a failed task with exponential backoff

        Args:
            db: Database session
            note_id: Note ID
            delay_seconds: Delay before retry
        """
        try:
            # Get queue entry
            result = await db.execute(
                select(ProcessingQueue).where(ProcessingQueue.note_id == note_id)
            )
            queue_entry = result.scalar_one_or_none()

            if not queue_entry:
                logger.error(f"Queue entry not found for note {note_id}")
                return

            # Increment retry count
            queue_entry.retry_count += 1
            queue_entry.status = QueueStatus.waiting

            # Calculate new priority (lower for retries)
            new_priority = max(0, queue_entry.priority - 1)
            queue_entry.priority = new_priority

            await db.commit()

            # Add back to Redis with delay (using timestamp in future)
            future_timestamp = int((datetime.utcnow() + timedelta(seconds=delay_seconds)).timestamp())
            score = (new_priority * 1000000) - future_timestamp
            self.redis_client.zadd(
                self.QUEUE_KEY,
                {str(note_id): score}
            )

            # Decrement processing counter
            self.redis_client.decr(self.PROCESSING_KEY)

            logger.info(f"Scheduled retry for note {note_id}. Retry count: {queue_entry.retry_count}")

        except Exception as e:
            logger.error(f"Error retrying task: {str(e)}", exc_info=True)

    async def get_queue_stats(self, db: AsyncSession) -> Dict:
        """
        Get queue statistics

        Args:
            db: Database session

        Returns:
            Dict with queue stats
        """
        try:
            # Queue length from Redis
            queue_length = self.redis_client.zcard(self.QUEUE_KEY)

            # Processing count
            processing_count = int(self.redis_client.get(self.PROCESSING_KEY) or 0)

            # Get counts by status from database
            result = await db.execute(
                select(
                    ProcessingQueue.status,
                    func.count(ProcessingQueue.id)
                )
                .group_by(ProcessingQueue.status)
            )
            status_counts = dict(result.all())

            return {
                'queue_length': queue_length,
                'processing_count': processing_count,
                'capacity': settings.MAX_CONCURRENT_PROCESSING,
                'available_slots': max(0, settings.MAX_CONCURRENT_PROCESSING - processing_count),
                'waiting_count': status_counts.get(QueueStatus.waiting, 0),
                'processing_db_count': status_counts.get(QueueStatus.processing, 0),
                'completed_count': status_counts.get(QueueStatus.completed, 0),
                'failed_count': status_counts.get(QueueStatus.failed, 0)
            }

        except Exception as e:
            logger.error(f"Error getting queue stats: {str(e)}", exc_info=True)
            return {}

    async def cleanup_stale_tasks(
        self,
        db: AsyncSession,
        timeout_minutes: int = 30
    ):
        """
        Clean up tasks that have been processing too long

        Args:
            db: Database session
            timeout_minutes: Timeout in minutes
        """
        try:
            timeout_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)

            result = await db.execute(
                select(ProcessingQueue)
                .where(
                    and_(
                        ProcessingQueue.status == QueueStatus.processing,
                        ProcessingQueue.started_at < timeout_time
                    )
                )
            )
            stale_tasks = result.scalars().all()

            for task in stale_tasks:
                logger.warning(f"Found stale task: note_id={task.note_id}")

                # Retry if under limit
                if task.retry_count < settings.MAX_RETRY_ATTEMPTS:
                    await self.retry_task(db, task.note_id, delay_seconds=120)
                else:
                    # Mark as failed
                    await self.mark_completed(
                        db,
                        task.note_id,
                        success=False,
                        error_message="Processing timeout"
                    )

            if stale_tasks:
                logger.info(f"Cleaned up {len(stale_tasks)} stale tasks")

        except Exception as e:
            logger.error(f"Error cleaning up stale tasks: {str(e)}", exc_info=True)


# Singleton instance
queue_manager = QueueManager()
