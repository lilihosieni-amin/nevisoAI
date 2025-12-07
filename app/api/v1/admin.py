"""
Admin Dashboard API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.db.session import get_db
from app.core.dependencies import get_current_user_from_cookie
from app.db.models import (
    User, Payment, PaymentStatus, Note, NoteStatus,
    ProcessingQueue, QueueStatus, CreditTransaction,
    UserSubscription, SubscriptionStatus
)
from app.services.monitoring_service import monitoring_service
from app.services.queue_service import queue_manager

router = APIRouter()


# TODO: Add proper admin authentication
def check_admin_access(current_user: User):
    """Check if user has admin access"""
    # For now, just check if user exists
    # In production, add role-based access control
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی غیرمجاز"
        )
    return current_user


class DashboardStatsResponse(BaseModel):
    total_users: int
    active_subscriptions: int
    total_revenue_today: float
    total_revenue_month: float
    notes_processed_today: int
    notes_failed_today: int
    queue_length: int
    processing_count: int
    system_healthy: bool


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت آمار کلی داشبورد

    Returns:
        آمار سیستم شامل کاربران، پرداخت‌ها، یادداشت‌ها، صف
    """
    check_admin_access(current_user)

    try:
        # Total users
        result = await db.execute(select(func.count(User.id)))
        total_users = result.scalar()

        # Active subscriptions
        result = await db.execute(
            select(func.count(UserSubscription.id))
            .where(
                and_(
                    UserSubscription.status == SubscriptionStatus.active,
                    UserSubscription.end_date > datetime.utcnow()
                )
            )
        )
        active_subscriptions = result.scalar()

        # Revenue today
        today = datetime.utcnow().date()
        result = await db.execute(
            select(func.sum(Payment.amount_toman))
            .where(
                and_(
                    Payment.status == PaymentStatus.completed,
                    func.date(Payment.paid_at) == today
                )
            )
        )
        revenue_today = float(result.scalar() or 0)

        # Revenue this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
        result = await db.execute(
            select(func.sum(Payment.amount_toman))
            .where(
                and_(
                    Payment.status == PaymentStatus.completed,
                    Payment.paid_at >= month_start
                )
            )
        )
        revenue_month = float(result.scalar() or 0)

        # Notes processed today
        result = await db.execute(
            select(func.count(Note.id))
            .where(
                and_(
                    Note.status == NoteStatus.completed,
                    func.date(Note.updated_at) == today
                )
            )
        )
        notes_processed_today = result.scalar()

        # Notes failed today
        result = await db.execute(
            select(func.count(Note.id))
            .where(
                and_(
                    Note.status == NoteStatus.failed,
                    func.date(Note.updated_at) == today
                )
            )
        )
        notes_failed_today = result.scalar()

        # Queue stats
        queue_stats = await queue_manager.get_queue_stats(db)

        # System health
        health = await monitoring_service.get_system_health(db)

        return DashboardStatsResponse(
            total_users=total_users,
            active_subscriptions=active_subscriptions,
            total_revenue_today=revenue_today,
            total_revenue_month=revenue_month,
            notes_processed_today=notes_processed_today,
            notes_failed_today=notes_failed_today,
            queue_length=queue_stats.get('queue_length', 0),
            processing_count=queue_stats.get('processing_count', 0),
            system_healthy=health.get('healthy', False)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت آمار: {str(e)}"
        )


@router.get("/dashboard/health")
async def get_system_health(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت وضعیت سلامت سیستم

    Returns:
        جزئیات کامل سلامت سیستم
    """
    check_admin_access(current_user)

    try:
        health = await monitoring_service.get_system_health(db)
        return health
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در بررسی سلامت: {str(e)}"
        )


@router.get("/dashboard/recent-payments")
async def get_recent_payments(
    limit: int = 20,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت آخرین پرداخت‌ها

    Args:
        limit: تعداد رکورد

    Returns:
        لیست پرداخت‌ها با اطلاعات کاربر
    """
    check_admin_access(current_user)

    try:
        result = await db.execute(
            select(Payment, User)
            .join(User, Payment.user_id == User.id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        payments = result.all()

        return [
            {
                'payment_id': p.id,
                'user_id': p.user_id,
                'user_phone': u.phone_number,
                'user_name': u.full_name,
                'amount': float(p.amount_toman),
                'status': p.status.value,
                'gateway': p.payment_gateway,
                'transaction_ref': p.transaction_ref_id,
                'paid_at': p.paid_at.isoformat() if p.paid_at else None,
                'created_at': p.created_at.isoformat()
            }
            for p, u in payments
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت پرداخت‌ها: {str(e)}"
        )


@router.get("/dashboard/failed-notes")
async def get_failed_notes(
    hours: int = 24,
    limit: int = 50,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت یادداشت‌های ناموفق

    Args:
        hours: بازه زمانی (ساعت)
        limit: تعداد رکورد

    Returns:
        لیست یادداشت‌های ناموفق با جزئیات خطا
    """
    check_admin_access(current_user)

    try:
        since = datetime.utcnow() - timedelta(hours=hours)

        result = await db.execute(
            select(Note, User)
            .join(User, Note.user_id == User.id)
            .where(
                and_(
                    Note.status == NoteStatus.failed,
                    Note.updated_at >= since
                )
            )
            .order_by(desc(Note.updated_at))
            .limit(limit)
        )
        notes = result.all()

        return [
            {
                'note_id': n.id,
                'title': n.title,
                'user_id': n.user_id,
                'user_phone': u.phone_number,
                'error_type': n.error_type,
                'error_message': n.error_message,
                'error_detail': n.error_detail,
                'retry_count': n.retry_count,
                'last_error_at': n.last_error_at.isoformat() if n.last_error_at else None,
                'created_at': n.created_at.isoformat()
            }
            for n, u in notes
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت یادداشت‌های ناموفق: {str(e)}"
        )


@router.get("/dashboard/queue-status")
async def get_detailed_queue_status(
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت وضعیت دقیق صف پردازش

    Returns:
        آمار تفصیلی صف
    """
    check_admin_access(current_user)

    try:
        stats = await queue_manager.get_queue_stats(db)

        # Get oldest waiting item
        result = await db.execute(
            select(ProcessingQueue)
            .where(ProcessingQueue.status == QueueStatus.waiting)
            .order_by(ProcessingQueue.added_at)
            .limit(1)
        )
        oldest_waiting = result.scalar_one_or_none()

        # Get longest processing item
        result = await db.execute(
            select(ProcessingQueue)
            .where(ProcessingQueue.status == QueueStatus.processing)
            .order_by(ProcessingQueue.started_at)
            .limit(1)
        )
        longest_processing = result.scalar_one_or_none()

        return {
            **stats,
            'oldest_waiting': {
                'note_id': oldest_waiting.note_id,
                'wait_time_minutes': int((datetime.utcnow() - oldest_waiting.added_at).total_seconds() / 60),
                'added_at': oldest_waiting.added_at.isoformat()
            } if oldest_waiting else None,
            'longest_processing': {
                'note_id': longest_processing.note_id,
                'processing_time_minutes': int((datetime.utcnow() - longest_processing.started_at).total_seconds() / 60),
                'started_at': longest_processing.started_at.isoformat()
            } if longest_processing else None
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت وضعیت صف: {str(e)}"
        )


@router.get("/dashboard/revenue-chart")
async def get_revenue_chart(
    days: int = 30,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت نمودار درآمد روزانه

    Args:
        days: تعداد روز

    Returns:
        آرایه درآمد روزانه
    """
    check_admin_access(current_user)

    try:
        since = datetime.utcnow() - timedelta(days=days)

        result = await db.execute(
            select(
                func.date(Payment.paid_at).label('date'),
                func.sum(Payment.amount_toman).label('total'),
                func.count(Payment.id).label('count')
            )
            .where(
                and_(
                    Payment.status == PaymentStatus.completed,
                    Payment.paid_at >= since
                )
            )
            .group_by(func.date(Payment.paid_at))
            .order_by(func.date(Payment.paid_at))
        )
        data = result.all()

        return [
            {
                'date': str(row.date),
                'revenue': float(row.total),
                'payment_count': row.count
            }
            for row in data
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت نمودار: {str(e)}"
        )


@router.get("/dashboard/top-users")
async def get_top_users(
    limit: int = 10,
    current_user: User = Depends(get_current_user_from_cookie),
    db: AsyncSession = Depends(get_db)
):
    """
    دریافت کاربران برتر بر اساس استفاده

    Args:
        limit: تعداد کاربر

    Returns:
        لیست کاربران با آمار استفاده
    """
    check_admin_access(current_user)

    try:
        # Get users with most notes
        result = await db.execute(
            select(
                User,
                func.count(Note.id).label('note_count'),
                func.sum(Payment.amount_toman).label('total_paid')
            )
            .outerjoin(Note, User.id == Note.user_id)
            .outerjoin(Payment, and_(
                User.id == Payment.user_id,
                Payment.status == PaymentStatus.completed
            ))
            .group_by(User.id)
            .order_by(desc('note_count'))
            .limit(limit)
        )
        users = result.all()

        return [
            {
                'user_id': u.id,
                'phone': u.phone_number,
                'name': u.full_name,
                'email': u.email,
                'note_count': note_count,
                'total_paid': float(total_paid or 0),
                'joined_at': u.created_at.isoformat()
            }
            for u, note_count, total_paid in users
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطا در دریافت کاربران برتر: {str(e)}"
        )
