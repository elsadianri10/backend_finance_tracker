"""Public package exports; modules load on demand to avoid circular imports."""
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import (
        auth_service,
        bank_account_service,
        billing_service,
        billing_transaction_service,
        debt_service,
        payment_sync_service,
        routine_service,
        savings_service,
        savings_sync_service,
        split_bill_service,
        split_bill_pdf,
        summary_service,
    )

__all__ = [
    'auth_service',
    'bank_account_service',
    'billing_service',
    'billing_transaction_service',
    'debt_service',
    'payment_sync_service',
    'routine_service',
    'savings_service',
    'savings_sync_service',
    'split_bill_service',
    'split_bill_pdf',
    'summary_service',
]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
