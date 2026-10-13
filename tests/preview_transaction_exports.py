"""Create synthetic export previews without accessing the application database."""
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import date
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.transaction_export_schema import TransactionExportInput
from app.services.transaction_export_service import pdf, excel

rows = []
for index in range(35):
    kind, category, amount = [('expense', 'food', 25000), ('income', 'salary', 1200000),
        ('income', 'cash_withdrawal', 500000), ('income', 'receivable', 150000), ('transfer', 'savings', 300000)][index % 5]
    rows.append(SimpleNamespace(id=uuid4(), kind=kind, category=category, amount=amount,
        transaction_date=date(2026, 10, 13-index % 10), description='Contoh transaksi ' + str(index+1),
        notes='Catatan contoh untuk pemeriksaan tata letak laporan.' if index % 3 == 0 else '',
        source_label='BCA Digital (BLU) · ********6201', destination_label='Tunai / Tidak dicatat'))
rows.sort(key=lambda row: row.transaction_date)
payload = TransactionExportInput.model_validate({'Month': '2026-10', 'TransactionIds': [str(row.id) for row in rows]})
root = Path(sys.argv[1])
root.mkdir(exist_ok=True, parents=True)
(root / 'transaction-report.pdf').write_bytes(pdf(rows, payload, 'Pengguna Contoh'))
(root / 'transaction-report.xlsx').write_bytes(excel(rows, payload, 'Pengguna Contoh'))
