from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal


class PlanBase(BaseModel):
    name: str
    price_toman: Decimal
    duration_days: int
    max_minutes: int
    max_notebooks: int
    features: Optional[List[str]] = None
    is_active: bool = True


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price_toman: Optional[Decimal] = None
    duration_days: Optional[int] = None
    max_minutes: Optional[int] = None
    max_notebooks: Optional[int] = None
    features: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PlanResponse(BaseModel):
    id: int
    name: str
    price: int  # For frontend compatibility
    duration_days: int
    minutes_limit: int  # For frontend compatibility
    features: List[str] = []
    is_featured: bool = False

    @classmethod
    def from_db_model(cls, plan):
        """Convert database model to response schema"""
        # Mark the middle-priced plan as featured (usually the most popular)
        is_featured = plan.id == 2 or "ماهانه" in plan.name or "حرفه" in plan.name
        
        return cls(
            id=plan.id,
            name=plan.name,
            price=int(plan.price_toman),
            duration_days=plan.duration_days,
            minutes_limit=plan.max_minutes,
            features=plan.features or [],
            is_featured=is_featured
        )

    class Config:
        from_attributes = True
