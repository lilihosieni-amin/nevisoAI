from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Plan
from typing import List, Optional


async def get_all_active_plans(db: AsyncSession) -> List[Plan]:
    """Get all active plans"""
    result = await db.execute(select(Plan).where(Plan.is_active == True))
    return list(result.scalars().all())


async def get_plan_by_id(db: AsyncSession, plan_id: int) -> Optional[Plan]:
    """Get plan by ID"""
    result = await db.execute(select(Plan).where(Plan.id == plan_id))
    return result.scalar_one_or_none()
