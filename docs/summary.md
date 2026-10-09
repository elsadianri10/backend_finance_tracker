# Ringkasan Keuangan

`GET /summary?month=YYYY-MM` is an authenticated, owner-scoped, no-store read-only aggregate. The Next.js `/api/summary` route projects only summary fields and names, without bank numbers or user identifiers.

- Monthly earnings exclude cash withdrawals and receivable repayments. Net cash flow is earnings + receivable repayments - expenses. Transfers, withdrawals, and savings allocations are shown separately.
- Only active ledger entries count. Linked payments count once; voided entries do not count.
- Savings balances, deposit principal, metal weights/estimates, debt balances/interest, account counts and fees are current values. They are not historical balances for the selected month.
- Bills summarize unpaid issued installments due in the selected month, plus a separate all-month overdue count/value as of today. Accrued subscriptions are projected without inserting installments. Future unissued subscription charges are not forecasts.
- Routine plans and payments use the scheduled due month, not the ledger payment date. A recorded cycle is complete even if its actual payment differs from its planned amount; pending is the sum of unpaid scheduled amounts, not planned minus actual paid.
- Routine and bill figures are not added together because they can refer to the same payment. NOTE plans do not contribute to planned/pending amounts.
- Split Bill only counts groups overlapping the selected month. Calculator totals are not personal expenses or completed settlements.
- Bank fees are estimates recorded in account settings, not automatically posted expenses. Metal estimates use the last saved prices and identify missing prices.

No schema migration, JSONB storage, financial backfill, or modification of user records is needed. Tests use synthetic in-memory SQLite only: `python -m unittest discover -s tests -p test_summary.py`. Frontend integration is covered in `npm run test:routines`.
