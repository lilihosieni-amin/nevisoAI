from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.schemas.plan import PlanResponse
from app.crud import plan as plan_crud
from typing import List

router = APIRouter()


@router.get("/", response_model=List[PlanResponse])
async def get_plans(db: AsyncSession = Depends(get_db)):
    """
    Get all active subscription plans (public endpoint)
    """
    plans = await plan_crud.get_all_active_plans(db)
    return [PlanResponse.from_db_model(plan) for plan in plans]
