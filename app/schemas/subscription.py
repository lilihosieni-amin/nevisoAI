from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class SubscriptionBase(BaseModel):
    user_id: int
    plan_id: int


class SubscriptionCreate(SubscriptionBase):
    start_date: datetime
    end_date: datetime


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    plan_id: int
    start_date: datetime
    end_date: datetime
    minutes_consumed: int
    status: str

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    plan_id: int


class PaymentResponse(BaseModel):
    payment_url: str


class PaymentCallbackResponse(BaseModel):
    success: bool
    message: str
    subscription_id: Optional[int] = None
