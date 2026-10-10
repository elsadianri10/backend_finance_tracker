"""Public package exports; modules load on demand to avoid circular imports."""
from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING

from .base_schema import PascalModel
from .auth_schema import GoogleLoginRequest, UserResponse, LoginResponse
from .bank_account_schema import BankAccountCreate, BankAccountUpdate, BankAccountResponse, WalletProviderResponse
from .billing_schema import PlatformType, BillingAccountCreate, BillingPlatformResponse, BillingAccountUpdate, BillingAccountResponse
from .billing_transaction_schema import TransactionCreate, LastAmountUpdate, InstallmentResponse as BillingInstallmentResponse, TransactionResponse
from .debt_schema import DebtKind, InterestType, DebtCreate, PaymentCreate, PaymentResponse, InterestChargeResponse, InstallmentResponse as DebtInstallmentResponse, InstallmentsUpdate, DebtResponse
from .routine_schema import RoutineInput, RoutineUpdate, PaymentInput, TransactionInput, LegacyTransaction, ImportInput
from .savings_schema import SavingCreate, MovementCreate, MovementResponse, SavingResponse
from .split_bill_schema import Participant, ItemShare, BillItem, Charge, Expense, GroupCreate, GroupUpdate

if TYPE_CHECKING:
    from . import (
        auth_schema,
        bank_account_schema,
        base_schema,
        billing_schema,
        billing_transaction_schema,
        debt_schema,
        routine_schema,
        savings_schema,
        split_bill_schema,
    )

__all__ = [
    'auth_schema',
    'bank_account_schema',
    'base_schema',
    'billing_schema',
    'billing_transaction_schema',
    'debt_schema',
    'routine_schema',
    'savings_schema',
    'split_bill_schema',
    'PascalModel',
    'GoogleLoginRequest',
    'UserResponse',
    'LoginResponse',
    'BankAccountCreate',
    'BankAccountUpdate',
    'BankAccountResponse',
    'WalletProviderResponse',
    'PlatformType',
    'BillingAccountCreate',
    'BillingPlatformResponse',
    'BillingAccountUpdate',
    'BillingAccountResponse',
    'TransactionCreate',
    'LastAmountUpdate',
    'BillingInstallmentResponse',
    'TransactionResponse',
    'DebtKind',
    'InterestType',
    'DebtCreate',
    'PaymentCreate',
    'PaymentResponse',
    'InterestChargeResponse',
    'DebtInstallmentResponse',
    'InstallmentsUpdate',
    'DebtResponse',
    'RoutineInput',
    'RoutineUpdate',
    'PaymentInput',
    'TransactionInput',
    'LegacyTransaction',
    'ImportInput',
    'SavingCreate',
    'MovementCreate',
    'MovementResponse',
    'SavingResponse',
    'Participant',
    'ItemShare',
    'BillItem',
    'Charge',
    'Expense',
    'GroupCreate',
    'GroupUpdate',
]


def __getattr__(name: str) -> ModuleType:
    if name in __all__:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
