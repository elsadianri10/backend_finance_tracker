"""Read-only UUID suppression manifest for controlled restore review; contains no email/name."""
import argparse,asyncio,csv,sys
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));load_dotenv(ROOT/'.env')
from sqlalchemy import select
from app.config.db_config import async_session,engine
from app.models import AccountDeletion
async def run(path):
    target=Path(path).resolve()
    if target.exists():raise RuntimeError('Refusing to overwrite a manifest')
    async with async_session() as db:
        rows=(await db.execute(select(AccountDeletion.subject_id,AccountDeletion.status,AccountDeletion.updated_at).where(AccountDeletion.status.in_(['CLEANUP','COMPLETED'])).order_by(AccountDeletion.updated_at))).all()
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',newline='',encoding='utf-8') as file:
        writer=csv.writer(file);writer.writerow(['subject_id','status','updated_at']);writer.writerows((str(row[0]),row[1],row[2].isoformat()) for row in rows)
    await engine.dispose();print('UUID suppression manifest exported. Review and reapply deletions in the isolated restore before enabling access.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);asyncio.run(run(parser.parse_args().output))
