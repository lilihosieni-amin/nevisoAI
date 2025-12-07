"""
Credit Management System
Handles credit calculation, deduction, and refunds with transaction logging
"""
import logging
import os
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    User, UserSubscription, SubscriptionStatus,
    CreditTransaction, TransactionType,
    Note, Upload
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when user doesn't have enough credits"""
    pass


class CreditCalculationError(Exception):
    """Raised when credit calculation fails"""
    pass


class CreditManager:
    """
    Manages user credits including:
    - Calculating required credits for files
    - Deducting credits from subscriptions
    - Refunding credits on errors
    - Logging all transactions
    """

    @staticmethod
    async def get_file_duration(file_path: str, file_type: str) -> float:
        """
        Get duration of audio/video file in seconds

        Args:
            file_path: Path to the file
            file_type: Type of file (audio/video)

        Returns:
            Duration in seconds

        Raises:
            CreditCalculationError: If duration cannot be determined
        """
        try:
            # For audio/video files, we need to extract duration
            # Using ffprobe (part of ffmpeg)
            if file_type in ['audio', 'video']:
                import subprocess
                import json

                # Check if file exists
                if not os.path.exists(file_path):
                    raise CreditCalculationError(f"File not found: {file_path}")

                # Use ffprobe to get duration
                cmd = [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    file_path
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode != 0:
                    logger.error(f"ffprobe failed: {result.stderr}")
                    raise CreditCalculationError("Could not determine file duration")

                # Parse JSON output
                data = json.loads(result.stdout)
                duration = float(data.get('format', {}).get('duration', 0))

                if duration <= 0:
                    raise CreditCalculationError("Invalid file duration")

                logger.info(f"File duration: {duration} seconds ({duration/60:.2f} minutes)")
                return duration

            else:
                # For images, return 0 (will be calculated differently)
                return 0

        except subprocess.TimeoutExpired:
            logger.error("ffprobe timeout")
            raise CreditCalculationError("Timeout while reading file")

        except FileNotFoundError:
            logger.error("ffprobe not found. Install ffmpeg.")
            raise CreditCalculationError("Media processing tool not available")

        except Exception as e:
            logger.error(f"Error getting file duration: {str(e)}", exc_info=True)
            raise CreditCalculationError(f"Could not process file: {str(e)}")

    @staticmethod
    async def calculate_file_credits(
        file_path: str,
        file_type: str
    ) -> float:
        """
        Calculate credits required for a file

        Args:
            file_path: Path to the file
            file_type: Type of file (MIME type or simple type)

        Returns:
            Credits required in minutes

        Raises:
            CreditCalculationError: If calculation fails
        """
        try:
            # Parse file type - handle MIME types like 'audio/mpeg', 'video/mp4', 'image/jpeg'
            file_type_lower = file_type.lower()

            if file_type_lower.startswith('audio/') or file_type_lower.startswith('video/') or file_type in ['audio', 'video']:
                # Determine main type for duration extraction
                main_type = 'audio' if file_type_lower.startswith('audio/') or file_type == 'audio' else 'video'

                # Get duration in seconds
                duration_seconds = await CreditManager.get_file_duration(
                    file_path, main_type
                )
                # Convert to minutes and round up
                credits = duration_seconds / 60.0
                logger.info(f"Calculated credits for {file_type}: {credits:.2f} minutes")
                return credits

            elif file_type_lower.startswith('image/') or file_type == 'image':
                # Fixed cost per image
                credits = settings.IMAGE_CREDIT_COST
                logger.info(f"Calculated credits for image: {credits} minutes")
                return credits

            else:
                logger.error(f"Unknown file type: {file_type}")
                raise CreditCalculationError(f"Unsupported file type: {file_type}")

        except Exception as e:
            logger.error(f"Credit calculation failed: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def calculate_note_credits(
        db: AsyncSession,
        note_id: int
    ) -> float:
        """
        Calculate total credits required for a note (all uploads)

        Args:
            db: Database session
            note_id: Note ID

        Returns:
            Total credits required in minutes
        """
        try:
            # Get all uploads for this note
            result = await db.execute(
                select(Upload).where(Upload.note_id == note_id)
            )
            uploads = result.scalars().all()

            if not uploads:
                logger.warning(f"No uploads found for note {note_id}")
                return 0.0

            total_credits = 0.0

            for upload in uploads:
                # Calculate credits for each file
                credits = await CreditManager.calculate_file_credits(
                    upload.storage_path,
                    upload.file_type
                )
                total_credits += credits

            logger.info(f"Total credits for note {note_id}: {total_credits:.2f} minutes")
            return total_credits

        except Exception as e:
            logger.error(f"Error calculating note credits: {str(e)}", exc_info=True)
            raise CreditCalculationError(f"Could not calculate credits: {str(e)}")

    @staticmethod
    async def get_user_balance(
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, any]:
        """
        Get user's total credit balance from all active subscriptions

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dict with total balance and breakdown by subscription
        """
        try:
            # Get all active subscriptions with plan eagerly loaded
            result = await db.execute(
                select(UserSubscription)
                .options(selectinload(UserSubscription.plan))
                .where(
                    and_(
                        UserSubscription.user_id == user_id,
                        UserSubscription.status == SubscriptionStatus.active,
                        UserSubscription.end_date > datetime.utcnow()
                    )
                )
                .order_by(UserSubscription.end_date.asc())  # Oldest first
            )
            subscriptions = result.scalars().all()

            total_balance = Decimal('0')
            details = []

            for sub in subscriptions:
                # Calculate remaining credits
                remaining = sub.plan.max_minutes - sub.minutes_consumed
                remaining = max(Decimal('0'), Decimal(str(remaining)))
                total_balance += remaining

                details.append({
                    'subscription_id': sub.id,
                    'plan_name': sub.plan.name,
                    'total_minutes': sub.plan.max_minutes,
                    'consumed_minutes': sub.minutes_consumed,
                    'remaining_minutes': float(remaining),
                    'expires_at': sub.end_date.isoformat()
                })

            return {
                'total_minutes': float(total_balance),
                'subscriptions': details
            }

        except Exception as e:
            logger.error(f"Error getting user balance: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def deduct_credits(
        db: AsyncSession,
        user_id: int,
        amount: float,
        note_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Deduct credits from user's active subscriptions

        Credits are deducted from oldest expiring subscriptions first.

        Args:
            db: Database session
            user_id: User ID
            amount: Credits to deduct (in minutes)
            note_id: Associated note ID (optional)
            description: Transaction description

        Returns:
            True if successful

        Raises:
            InsufficientCreditsError: If user doesn't have enough credits
        """
        try:
            amount_decimal = Decimal(str(amount))

            # Get current balance
            balance_info = await CreditManager.get_user_balance(db, user_id)
            current_balance = Decimal(str(balance_info['total_minutes']))

            logger.info(f"Deducting {amount} minutes from user {user_id}. Current balance: {current_balance}")

            # Check if user has enough credits
            if current_balance < amount_decimal:
                logger.warning(f"Insufficient credits: need {amount}, have {current_balance}")
                raise InsufficientCreditsError(
                    f"اعتبار کافی نیست. موجودی: {current_balance:.1f} دقیقه، نیاز: {amount:.1f} دقیقه"
                )

            # Get active subscriptions ordered by expiry date (oldest first) with plan loaded
            result = await db.execute(
                select(UserSubscription)
                .options(selectinload(UserSubscription.plan))
                .where(
                    and_(
                        UserSubscription.user_id == user_id,
                        UserSubscription.status == SubscriptionStatus.active,
                        UserSubscription.end_date > datetime.utcnow()
                    )
                )
                .order_by(UserSubscription.end_date.asc())
            )
            subscriptions = result.scalars().all()

            # Deduct from subscriptions
            remaining_to_deduct = amount_decimal

            for sub in subscriptions:
                if remaining_to_deduct <= 0:
                    break

                # Calculate available credits in this subscription
                available = Decimal(str(sub.plan.max_minutes)) - Decimal(str(sub.minutes_consumed))
                available = max(Decimal('0'), available)

                if available <= 0:
                    continue

                # Deduct from this subscription
                deduct_from_this = min(available, remaining_to_deduct)

                balance_before = current_balance
                sub.minutes_consumed = float(Decimal(str(sub.minutes_consumed)) + deduct_from_this)
                current_balance -= deduct_from_this

                # Log transaction
                transaction = CreditTransaction(
                    user_id=user_id,
                    subscription_id=sub.id,
                    note_id=note_id,
                    transaction_type=TransactionType.deduct,
                    amount=float(deduct_from_this),
                    balance_before=float(balance_before),
                    balance_after=float(current_balance),
                    description=description or f"پردازش یادداشت #{note_id}"
                )
                db.add(transaction)

                remaining_to_deduct -= deduct_from_this

                logger.info(
                    f"Deducted {deduct_from_this} minutes from subscription {sub.id}. "
                    f"New consumed: {sub.minutes_consumed}"
                )

            # Commit all changes
            await db.commit()

            logger.info(f"Successfully deducted {amount} minutes from user {user_id}")
            return True

        except InsufficientCreditsError:
            await db.rollback()
            raise

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deducting credits: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def refund_credits(
        db: AsyncSession,
        user_id: int,
        amount: float,
        note_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Refund credits to user's subscriptions (in case of processing error)

        Credits are refunded to the most recently used subscriptions first.

        Args:
            db: Database session
            user_id: User ID
            amount: Credits to refund (in minutes)
            note_id: Associated note ID (optional)
            description: Transaction description

        Returns:
            True if successful
        """
        try:
            amount_decimal = Decimal(str(amount))

            logger.info(f"Refunding {amount} minutes to user {user_id}")

            # Get current balance
            balance_info = await CreditManager.get_user_balance(db, user_id)
            current_balance = Decimal(str(balance_info['total_minutes']))

            # Get recent deduct transactions for this note to know which subscriptions to refund
            result = await db.execute(
                select(CreditTransaction)
                .where(
                    and_(
                        CreditTransaction.user_id == user_id,
                        CreditTransaction.note_id == note_id,
                        CreditTransaction.transaction_type == TransactionType.deduct
                    )
                )
                .order_by(desc(CreditTransaction.created_at))
            )
            deduct_transactions = result.scalars().all()

            remaining_to_refund = amount_decimal

            # Refund to the same subscriptions (in reverse order)
            for trans in deduct_transactions:
                if remaining_to_refund <= 0:
                    break

                if not trans.subscription_id:
                    continue

                # Get subscription
                result = await db.execute(
                    select(UserSubscription)
                    .where(UserSubscription.id == trans.subscription_id)
                )
                sub = result.scalar_one_or_none()

                if not sub:
                    continue

                # Refund to this subscription
                refund_to_this = min(Decimal(str(trans.amount)), remaining_to_refund)

                balance_before = current_balance
                sub.minutes_consumed = max(
                    0,
                    float(Decimal(str(sub.minutes_consumed)) - refund_to_this)
                )
                current_balance += refund_to_this

                # Log refund transaction
                refund_transaction = CreditTransaction(
                    user_id=user_id,
                    subscription_id=sub.id,
                    note_id=note_id,
                    transaction_type=TransactionType.refund,
                    amount=float(refund_to_this),
                    balance_before=float(balance_before),
                    balance_after=float(current_balance),
                    description=description or f"بازگشت اعتبار یادداشت #{note_id}"
                )
                db.add(refund_transaction)

                remaining_to_refund -= refund_to_this

                logger.info(
                    f"Refunded {refund_to_this} minutes to subscription {sub.id}. "
                    f"New consumed: {sub.minutes_consumed}"
                )

            # Commit all changes
            await db.commit()

            logger.info(f"Successfully refunded {amount} minutes to user {user_id}")
            return True

        except Exception as e:
            await db.rollback()
            logger.error(f"Error refunding credits: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def log_purchase_transaction(
        db: AsyncSession,
        user_id: int,
        subscription_id: int,
        amount: float,
        description: Optional[str] = None
    ):
        """
        Log a credit purchase transaction

        Args:
            db: Database session
            user_id: User ID
            subscription_id: New subscription ID
            amount: Credits purchased (in minutes)
            description: Transaction description
        """
        try:
            # Get current balance
            balance_info = await CreditManager.get_user_balance(db, user_id)
            balance_before = Decimal(str(balance_info['total_minutes']))
            balance_after = balance_before + Decimal(str(amount))

            # Log transaction
            transaction = CreditTransaction(
                user_id=user_id,
                subscription_id=subscription_id,
                transaction_type=TransactionType.purchase,
                amount=float(amount),
                balance_before=float(balance_before),
                balance_after=float(balance_after),
                description=description or "خرید اشتراک"
            )
            db.add(transaction)
            await db.commit()

            logger.info(f"Logged purchase transaction: {amount} minutes for user {user_id}")

        except Exception as e:
            await db.rollback()
            logger.error(f"Error logging purchase transaction: {str(e)}", exc_info=True)

    @staticmethod
    async def get_user_transactions(
        db: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get user's credit transaction history

        Args:
            db: Database session
            user_id: User ID
            limit: Number of records to return
            offset: Offset for pagination

        Returns:
            List of transaction dicts
        """
        try:
            result = await db.execute(
                select(CreditTransaction)
                .where(CreditTransaction.user_id == user_id)
                .order_by(desc(CreditTransaction.created_at))
                .limit(limit)
                .offset(offset)
            )
            transactions = result.scalars().all()

            return [
                {
                    'id': trans.id,
                    'type': trans.transaction_type.value,
                    'amount': float(trans.amount),
                    'balance_before': float(trans.balance_before),
                    'balance_after': float(trans.balance_after),
                    'description': trans.description,
                    'note_id': trans.note_id,
                    'subscription_id': trans.subscription_id,
                    'created_at': trans.created_at.isoformat()
                }
                for trans in transactions
            ]

        except Exception as e:
            logger.error(f"Error getting user transactions: {str(e)}", exc_info=True)
            raise


# Create singleton instance
credit_manager = CreditManager()
