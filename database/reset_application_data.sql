-- Destructive maintenance for an explicitly confirmed database and schema.
-- Set finance_tracker.confirm_reset to current_database() || '.' || current_schema()
-- in the same session. This script preserves wallet providers, pending Blob cleanup, and unrelated tables.
DO $$
DECLARE
    target_schema text := current_schema();
    target text := current_database() || '.' || target_schema;
BEGIN
    IF target IS NULL OR current_setting('finance_tracker.confirm_reset', true) IS DISTINCT FROM target THEN
        RAISE EXCEPTION 'Reset dibatalkan: konfirmasi database dan schema tujuan diperlukan.';
    END IF;

    -- Consume confirmation and prevent fallback to tables in another schema.
    PERFORM set_config('finance_tracker.confirm_reset', '', false);
    EXECUTE format($reset$
    TRUNCATE TABLE
        %1$I.shared_subscription_receipts, %1$I.shared_subscription_waivers,
        %1$I.shared_subscription_members, %1$I.shared_subscriptions,
        %1$I.budget_items, %1$I.budget_categories, %1$I.budgets,
        %1$I.split_bill_links, %1$I.user_admin_audit, %1$I.account_deletion_blobs, %1$I.account_deletions,
        %1$I.subscription_payments, %1$I.subscription_orders, %1$I.access_audit, %1$I.account_access,
        %1$I.stock_events, %1$I.stock_products, %1$I.stock_needs, %1$I.wishlist_reservations,
        %1$I.wishlist_photos, %1$I.wishlist_items, %1$I.wishlist_groups, %1$I.wishlists,
        %1$I.user_passkeys, %1$I.passkey_challenges, %1$I.passkey_recovery_codes, %1$I.ledger_transactions,
        %1$I.routine_payments, %1$I.routine_plans, %1$I.transaction_imports, %1$I.split_bill_shares,
        %1$I.split_bill_items, %1$I.split_bill_expenses, %1$I.split_bill_participants, %1$I.split_bill_groups,
        %1$I.saving_movements, %1$I.savings, %1$I.bank_accounts, %1$I.debt_payments,
        %1$I.debt_installments, %1$I.debts, %1$I.billing_installments, %1$I.billing_transactions,
        %1$I.billing_accounts, %1$I.users
    RESTART IDENTITY
    $reset$, target_schema);
END $$;
