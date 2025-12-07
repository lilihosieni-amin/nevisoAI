"""
Test Cases for Credit Management System
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.credit_service import (
    credit_manager,
    InsufficientCreditsError,
    CreditCalculationError
)
from app.db.models import (
    Base, User, Plan, UserSubscription, SubscriptionStatus,
    CreditTransaction, TransactionType
)


# Test database URL (use SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create test database session"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create test user"""
    user = User(
        phone_number="09123456789",
        email="test@example.com",
        full_name="Test User"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_plan(db_session: AsyncSession):
    """Create test plan"""
    plan = Plan(
        name="تست پلن",
        price_toman=100000,
        duration_days=30,
        max_minutes=60,
        max_notebooks=10,
        is_active=True
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest.fixture
async def test_subscription(db_session: AsyncSession, test_user, test_plan):
    """Create test subscription"""
    subscription = UserSubscription(
        user_id=test_user.id,
        plan_id=test_plan.id,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),
        minutes_consumed=0,
        status=SubscriptionStatus.active
    )
    db_session.add(subscription)
    await db_session.commit()
    await db_session.refresh(subscription)
    return subscription


class TestCreditBalance:
    """Test credit balance calculation"""

    @pytest.mark.asyncio
    async def test_get_balance_no_subscriptions(self, db_session, test_user):
        """Test balance with no subscriptions"""
        balance = await credit_manager.get_user_balance(db_session, test_user.id)

        assert balance['total_minutes'] == 0
        assert len(balance['subscriptions']) == 0

    @pytest.mark.asyncio
    async def test_get_balance_with_subscription(
        self, db_session, test_user, test_subscription
    ):
        """Test balance with active subscription"""
        balance = await credit_manager.get_user_balance(db_session, test_user.id)

        assert balance['total_minutes'] == 60.0
        assert len(balance['subscriptions']) == 1
        assert balance['subscriptions'][0]['remaining_minutes'] == 60.0

    @pytest.mark.asyncio
    async def test_get_balance_partially_consumed(
        self, db_session, test_user, test_subscription
    ):
        """Test balance with partially consumed subscription"""
        # Consume some credits
        test_subscription.minutes_consumed = 20
        await db_session.commit()

        balance = await credit_manager.get_user_balance(db_session, test_user.id)

        assert balance['total_minutes'] == 40.0
        assert balance['subscriptions'][0]['remaining_minutes'] == 40.0
        assert balance['subscriptions'][0]['consumed_minutes'] == 20


class TestCreditDeduction:
    """Test credit deduction"""

    @pytest.mark.asyncio
    async def test_deduct_credits_success(
        self, db_session, test_user, test_subscription
    ):
        """Test successful credit deduction"""
        result = await credit_manager.deduct_credits(
            db_session,
            test_user.id,
            amount=10.5,
            description="Test deduction"
        )

        assert result is True

        # Check updated balance
        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 49.5

        # Check subscription updated
        await db_session.refresh(test_subscription)
        assert test_subscription.minutes_consumed == 10.5

    @pytest.mark.asyncio
    async def test_deduct_credits_insufficient(
        self, db_session, test_user, test_subscription
    ):
        """Test deduction with insufficient credits"""
        with pytest.raises(InsufficientCreditsError):
            await credit_manager.deduct_credits(
                db_session,
                test_user.id,
                amount=100.0,  # More than available
                description="Test deduction"
            )

        # Balance should be unchanged
        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 60.0

    @pytest.mark.asyncio
    async def test_deduct_credits_exact_amount(
        self, db_session, test_user, test_subscription
    ):
        """Test deducting exact available amount"""
        result = await credit_manager.deduct_credits(
            db_session,
            test_user.id,
            amount=60.0,
            description="Test deduction"
        )

        assert result is True

        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 0.0

    @pytest.mark.asyncio
    async def test_deduct_credits_transaction_logged(
        self, db_session, test_user, test_subscription
    ):
        """Test that deduction is logged"""
        await credit_manager.deduct_credits(
            db_session,
            test_user.id,
            amount=15.0,
            description="Test logging"
        )

        # Check transaction was created
        from sqlalchemy import select
        result = await db_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.user_id == test_user.id
            )
        )
        transactions = result.scalars().all()

        assert len(transactions) == 1
        trans = transactions[0]
        assert trans.transaction_type == TransactionType.deduct
        assert trans.amount == 15.0
        assert trans.balance_before == 60.0
        assert trans.balance_after == 45.0


class TestCreditRefund:
    """Test credit refund"""

    @pytest.mark.asyncio
    async def test_refund_credits(
        self, db_session, test_user, test_subscription
    ):
        """Test refunding credits"""
        # First deduct
        await credit_manager.deduct_credits(
            db_session, test_user.id, 20.0, note_id=1
        )

        # Then refund
        result = await credit_manager.refund_credits(
            db_session,
            test_user.id,
            amount=20.0,
            note_id=1,
            description="Test refund"
        )

        assert result is True

        # Balance should be restored
        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 60.0

    @pytest.mark.asyncio
    async def test_refund_partial(
        self, db_session, test_user, test_subscription
    ):
        """Test partial refund"""
        # Deduct 30
        await credit_manager.deduct_credits(
            db_session, test_user.id, 30.0, note_id=1
        )

        # Refund only 10
        await credit_manager.refund_credits(
            db_session, test_user.id, 10.0, note_id=1
        )

        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 40.0


class TestMultipleSubscriptions:
    """Test with multiple subscriptions"""

    @pytest.mark.asyncio
    async def test_deduct_from_oldest_first(
        self, db_session, test_user, test_plan
    ):
        """Test that credits are deducted from oldest expiring subscription first"""
        # Create two subscriptions with different end dates
        sub1 = UserSubscription(
            user_id=test_user.id,
            plan_id=test_plan.id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=10),  # Expires first
            minutes_consumed=0,
            status=SubscriptionStatus.active
        )
        sub2 = UserSubscription(
            user_id=test_user.id,
            plan_id=test_plan.id,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=30),  # Expires later
            minutes_consumed=0,
            status=SubscriptionStatus.active
        )
        db_session.add_all([sub1, sub2])
        await db_session.commit()

        # Total balance should be 120 (60 + 60)
        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 120.0

        # Deduct 70 (should use all of sub1 and 10 of sub2)
        await credit_manager.deduct_credits(db_session, test_user.id, 70.0)

        # Check subscriptions
        await db_session.refresh(sub1)
        await db_session.refresh(sub2)

        assert sub1.minutes_consumed == 60.0  # Fully consumed
        assert sub2.minutes_consumed == 10.0

        # Remaining balance
        balance = await credit_manager.get_user_balance(db_session, test_user.id)
        assert balance['total_minutes'] == 50.0


class TestCreditCalculation:
    """Test credit calculation for files"""

    @pytest.mark.asyncio
    async def test_calculate_image_credits(self):
        """Test calculating credits for image"""
        from app.core.config import settings

        # Image should have fixed cost
        credits = await credit_manager.calculate_file_credits(
            "/path/to/image.jpg",
            "image"
        )

        assert credits == settings.IMAGE_CREDIT_COST

    # Note: Audio/video tests would require actual files or mocking ffprobe
