"""Generate a synthetic 20-person PDF without opening the application DB."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.schemas.split_bill_schema import GroupCreate
from app.services.split_bill_service import calculate
from app.services.split_bill_pdf import export_pdf
people = [{'Id':str(uuid4()),'Name':f'Peserta {i+1} - Contoh'} for i in range(20)]
items = [{'Id':str(uuid4()),'Name':f'Menu {i+1} - Makanan bersama dengan keterangan tambahan','Amount':15000+i,'SplitMode':'EQUAL','Shares':[{'ParticipantId':p['Id'],'Amount':0} for p in people]} for i in range(12)]
expenses = [{'Id':str(uuid4()),'Name':name,'ExpenseDate':'2026-10-09','PaidBy':people[i]['Id'],'Items':items,'ServiceCharge':{'Mode':'AMOUNT','Value':10528},'Tax':{'Mode':'PERCENT','Value':10},'ReceiptTotal':209000,'Notes':'Data sintetis untuk pemeriksaan tata letak PDF.'} for i,name in enumerate(['Makan Bersama','Kegiatan Berikutnya'])]
payload = GroupCreate.model_validate({'Name':'Contoh Grup - 20 Peserta','StartDate':'2026-10-01','EndDate':'2026-10-31','Participants':people,'Expenses':expenses})
group = payload.model_dump(mode='json',by_alias=True) | {'Calculation':calculate(payload)}
Path(sys.argv[1]).write_bytes(export_pdf(group))
