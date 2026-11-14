"""Read-only release checks. Prints status labels, never secret values."""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));load_dotenv(ROOT/'.env')
from app.config.db_config import engine
from sqlalchemy import text

def configured(*names):return all(bool(os.getenv(name,'').strip()) for name in names)
def report(label,ok):print(('PASS: ' if ok else 'PENDING: ')+label)
async def check():
    report('Payment gateway enabled',os.getenv('MIDTRANS_ENABLED','false').lower()=='true')
    report('Merchant production environment',os.getenv('MIDTRANS_ENVIRONMENT')=='production')
    report('Merchant credentials configured',configured('MIDTRANS_SERVER_KEY','MIDTRANS_WEBHOOK_TOKEN'))
    report('Recurring enabled',os.getenv('MIDTRANS_RECURRING_ENABLED','false').lower()=='true')
    report('Separate backup encryption key configured',configured('BACKUP_ENCRYPTION_KEY'))
    local=engine.url.host in {'localhost','127.0.0.1','::1'}
    print('INFO: database scope is '+('local; hosted readiness unverified' if local else 'hosted; queries are read-only'))
    report('Hosted database TLS configured',not local and os.getenv('DB_SSL','false').lower() in {'true','yes','1'})
    async with engine.connect() as db:
        for table,column in [('bank_accounts','archived'),('savings','archived'),('account_access','trial_until'),('subscription_orders','next_charge_at'),('subscription_payments','period_end'),('account_deletions','status'),('account_deletion_blobs','url'),('users','admin_f'),('user_admin_audit','admin_f')]:
            exists=await db.scalar(text('SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=:table AND column_name=:column)'),{'table':table,'column':column})
            report(table+'.'+column+' exists',exists)
        exists=await db.scalar(text("SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='users' AND column_name='admin_f')"))
        report('Database has an active admin',bool(await db.scalar(text('SELECT COUNT(*) FROM users WHERE admin_f=1 AND is_active=true'))) if exists else False)
    await engine.dispose()
    print('PENDING: verify frontend public-policy approval, merchant Sandbox scenarios, hosted backup/restore, retention and support operationally. This script does not certify production readiness.')
if __name__=='__main__':asyncio.run(check())
