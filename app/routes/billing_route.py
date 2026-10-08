from fastapi import APIRouter

from app.controllers import billing_controller as controller
from app.schemas.billing_schema import BillingAccountResponse, BillingPlatformResponse
from app.controllers import billing_transaction_controller as transactions
from app.schemas.billing_transaction_schema import TransactionResponse

router = APIRouter(prefix="/billing", tags=["Billing"])
router.add_api_route("/platforms", controller.platforms, methods=["GET"], response_model=list[BillingPlatformResponse])
router.add_api_route("/accounts", controller.add_account, methods=["POST"], response_model=BillingAccountResponse, status_code=201)
router.add_api_route("/accounts", controller.accounts, methods=["GET"], response_model=list[BillingAccountResponse])
router.add_api_route("/accounts/{account_id}", controller.account, methods=["GET"], response_model=BillingAccountResponse)
router.add_api_route("/accounts/{account_id}", controller.update_account, methods=["PATCH"], response_model=BillingAccountResponse)
router.add_api_route("/accounts/{account_id}", controller.delete_account, methods=["DELETE"], status_code=204)

router.add_api_route("/accounts/{account_id}/transactions", transactions.create, methods=["POST"], response_model=TransactionResponse, status_code=201)
router.add_api_route("/accounts/{account_id}/transactions", transactions.list_transactions, methods=["GET"], response_model=list[TransactionResponse])
router.add_api_route("/transactions/{transaction_id}", transactions.detail, methods=["GET"], response_model=TransactionResponse)
router.add_api_route("/transactions/{transaction_id}/installments/{installment_id}/pay", transactions.mark_paid, methods=["POST"], response_model=TransactionResponse)
router.add_api_route("/transactions/{transaction_id}/last-amount", transactions.update_last, methods=["PATCH"], response_model=TransactionResponse)
router.add_api_route("/transactions/{transaction_id}/subscription-amount", transactions.update_subscription, methods=["PATCH"], response_model=TransactionResponse)
router.add_api_route("/transactions/{transaction_id}/stop", transactions.stop_subscription, methods=["POST"], response_model=TransactionResponse)
router.add_api_route("/transactions/{transaction_id}", transactions.delete_subscription, methods=["DELETE"], status_code=204)
