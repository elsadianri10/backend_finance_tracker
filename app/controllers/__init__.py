"""Public package exports; modules load on demand to avoid circular imports."""
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING
from .version_controller import get_version

if TYPE_CHECKING:
    from . import wishlist_controller
    from . import transaction_export_controller
    from . import passkey_controller
    from . import (
        auth_controller,
        bank_account_controller,
        billing_controller,
        billing_transaction_controller,
        debt_controller,
        routine_controller,
        savings_controller,
        split_bill_controller,
        summary_controller,
        version_controller,
    )

__all__ = [
    "wishlist_controller",
    "transaction_export_controller",
    "passkey_controller",
    'auth_controller',
    'bank_account_controller',
    'billing_controller',
    'billing_transaction_controller',
    'debt_controller',
    'routine_controller',
    'savings_controller',
    'split_bill_controller',
    'summary_controller',
    'version_controller',
    'get_version',
]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
