"""
Monitoring and Alert System
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ProcessingQueue, QueueStatus,
    Payment, PaymentStatus,
    Note, NoteStatus
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    System health monitoring and alerting
    """

    @staticmethod
    async def check_queue_health(db: AsyncSession) -> Dict:
        """
        Check queue system health

        Returns:
            Health status dict
        """
        try:
            # Get queue length
            result = await db.execute(
                select(func.count(ProcessingQueue.id))
                .where(ProcessingQueue.status == QueueStatus.waiting)
            )
            queue_length = result.scalar()

            # Get processing count
            result = await db.execute(
                select(func.count(ProcessingQueue.id))
                .where(ProcessingQueue.status == QueueStatus.processing)
            )
            processing_count = result.scalar()

            # Check stale tasks (processing > 30 mins)
            stale_time = datetime.utcnow() - timedelta(minutes=30)
            result = await db.execute(
                select(func.count(ProcessingQueue.id))
                .where(
                    and_(
                        ProcessingQueue.status == QueueStatus.processing,
                        ProcessingQueue.started_at < stale_time
                    )
                )
            )
            stale_count = result.scalar()

            # Determine health status
            issues = []
            if queue_length > 100:
                issues.append(f"Queue too long: {queue_length} items")
            if stale_count > 0:
                issues.append(f"Stale tasks detected: {stale_count}")
            if processing_count >= settings.MAX_CONCURRENT_PROCESSING:
                issues.append("At max processing capacity")

            return {
                'healthy': len(issues) == 0,
                'queue_length': queue_length,
                'processing_count': processing_count,
                'stale_count': stale_count,
                'issues': issues
            }

        except Exception as e:
            logger.error(f"Error checking queue health: {str(e)}", exc_info=True)
            return {
                'healthy': False,
                'error': str(e)
            }

    @staticmethod
    async def check_processing_error_rate(
        db: AsyncSession,
        hours: int = 1
    ) -> Dict:
        """
        Check processing error rate

        Args:
            hours: Time window in hours

        Returns:
            Error rate stats
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Total completed/failed in window
            result = await db.execute(
                select(func.count(Note.id))
                .where(
                    and_(
                        Note.updated_at >= since,
                        Note.status.in_([NoteStatus.completed, NoteStatus.failed])
                    )
                )
            )
            total = result.scalar()

            # Failed count
            result = await db.execute(
                select(func.count(Note.id))
                .where(
                    and_(
                        Note.updated_at >= since,
                        Note.status == NoteStatus.failed
                    )
                )
            )
            failed = result.scalar()

            # Calculate error rate
            error_rate = (failed / total * 100) if total > 0 else 0

            issues = []
            if error_rate > 10:
                issues.append(f"High error rate: {error_rate:.1f}%")

            return {
                'healthy': error_rate <= 10,
                'error_rate': error_rate,
                'total_processed': total,
                'failed_count': failed,
                'issues': issues
            }

        except Exception as e:
            logger.error(f"Error checking error rate: {str(e)}", exc_info=True)
            return {
                'healthy': False,
                'error': str(e)
            }

    @staticmethod
    async def check_payment_failures(
        db: AsyncSession,
        hours: int = 1
    ) -> Dict:
        """
        Check payment failure rate

        Args:
            hours: Time window in hours

        Returns:
            Payment failure stats
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Total payments in window
            result = await db.execute(
                select(func.count(Payment.id))
                .where(Payment.created_at >= since)
            )
            total = result.scalar()

            # Failed payments
            result = await db.execute(
                select(func.count(Payment.id))
                .where(
                    and_(
                        Payment.created_at >= since,
                        Payment.status == PaymentStatus.failed
                    )
                )
            )
            failed = result.scalar()

            failure_rate = (failed / total * 100) if total > 0 else 0

            issues = []
            if failed > 5:
                issues.append(f"Multiple payment failures: {failed}")
            if failure_rate > 20:
                issues.append(f"High failure rate: {failure_rate:.1f}%")

            return {
                'healthy': failed <= 5 and failure_rate <= 20,
                'failure_rate': failure_rate,
                'total_payments': total,
                'failed_count': failed,
                'issues': issues
            }

        except Exception as e:
            logger.error(f"Error checking payment failures: {str(e)}", exc_info=True)
            return {
                'healthy': False,
                'error': str(e)
            }

    @staticmethod
    async def get_system_health(db: AsyncSession) -> Dict:
        """
        Get overall system health

        Returns:
            Complete health status
        """
        try:
            queue_health = await MonitoringService.check_queue_health(db)
            error_rate = await MonitoringService.check_processing_error_rate(db)
            payment_health = await MonitoringService.check_payment_failures(db)

            all_healthy = (
                queue_health.get('healthy', False) and
                error_rate.get('healthy', False) and
                payment_health.get('healthy', False)
            )

            return {
                'healthy': all_healthy,
                'timestamp': datetime.utcnow().isoformat(),
                'queue': queue_health,
                'processing': error_rate,
                'payments': payment_health
            }

        except Exception as e:
            logger.error(f"Error getting system health: {str(e)}", exc_info=True)
            return {
                'healthy': False,
                'error': str(e)
            }

    @staticmethod
    async def send_alert(
        message: str,
        severity: str = 'warning',
        details: Optional[Dict] = None
    ):
        """
        Send alert notification

        Args:
            message: Alert message
            severity: 'info', 'warning', 'error', 'critical'
            details: Additional details
        """
        try:
            # Log alert
            log_func = {
                'info': logger.info,
                'warning': logger.warning,
                'error': logger.error,
                'critical': logger.critical
            }.get(severity, logger.warning)

            log_message = f"[ALERT] {message}"
            if details:
                log_message += f" | Details: {details}"

            log_func(log_message)

            # TODO: Implement actual alert delivery
            # - Send to Telegram bot
            # - Send email to admin
            # - Trigger webhook
            # For now, just logging

        except Exception as e:
            logger.error(f"Error sending alert: {str(e)}", exc_info=True)


# Singleton instance
monitoring_service = MonitoringService()
