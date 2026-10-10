from .version_route import router as version_router
from .auth_route import router as auth_router
from .billing_route import router as billing_router
from .bank_account_route import router as bank_account_router
from .debt_route import router as debt_router
from .routine_route import router as routine_router
from .savings_route import router as savings_router
from .split_bill_route import router as split_bill_router
from .summary_route import router as summary_router

__all__ = [
    "version_router", "auth_router", "billing_router", "bank_account_router",
    "debt_router", "routine_router", "savings_router", "split_bill_router", "summary_router",
]
