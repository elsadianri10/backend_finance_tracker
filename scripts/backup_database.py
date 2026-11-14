"""Create an AES-GCM encrypted PostgreSQL custom dump. Does not restore or delete data."""
import argparse,os,subprocess,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));load_dotenv(ROOT/'.env')
from app.config.db_config import DATABASE_URL
MAGIC=b'FINANCE-PGDUMP-1\n'
def key():
    try:result=bytes.fromhex(os.environ['BACKUP_ENCRYPTION_KEY'])
    except (KeyError,ValueError):raise ValueError('Set BACKUP_ENCRYPTION_KEY to a separate 64-character hex secret; never pass it on the command line') from None
    if len(result)!=32:raise ValueError('BACKUP_ENCRYPTION_KEY must encode exactly 32 bytes')
    return result

def encrypt(data,secret):
    nonce=os.urandom(12);return MAGIC+nonce+AESGCM(secret).encrypt(nonce,data,MAGIC)
def decrypt(data,secret):
    if not data.startswith(MAGIC):raise ValueError('Unsupported backup format')
    offset=len(MAGIC);return AESGCM(secret).decrypt(data[offset:offset+12],data[offset+12:],MAGIC)
def run(output,hosted=False):
    secret=key();url=DATABASE_URL
    if url.host not in {'localhost','127.0.0.1','::1'} and not hosted:raise ValueError('Hosted backup requires --allow-hosted; this only reads the database')
    target=Path(output).resolve()
    if target.exists():raise ValueError('Refusing to overwrite an existing backup')
    if target.suffix!='.ftbackup':raise ValueError('Use the .ftbackup extension')
    binary=Path(os.getenv('PG_BIN',r'C:/Program Files/PostgreSQL/16/bin'))/'pg_dump.exe'
    env=os.environ|{'PGHOST':url.host or 'localhost','PGPORT':str(url.port or 5432),'PGUSER':url.username or '', 'PGPASSWORD':url.password or '', 'PGDATABASE':url.database or ''}
    if os.getenv('DB_SSL','false').lower() in {'true','1','yes'}:env['PGSSLMODE']='verify-full'
    with tempfile.TemporaryDirectory(prefix='finance-private-backup-') as directory:
        dump=Path(directory)/'database.dump'
        result=subprocess.run([str(binary),'--format=custom','--no-owner','--no-privileges','--file',str(dump)],env=env,capture_output=True)
        if result.returncode:raise RuntimeError('pg_dump failed; no backup written (check client version and connection privately)')
        data=dump.read_bytes();encrypted=encrypt(data,secret)
        assert decrypt(encrypted,secret)==data
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as saved:saved.write(encrypted)
    print('Encrypted backup written and authenticated locally. Store the key separately. Restore to an isolated database must still be tested.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);parser.add_argument('--allow-hosted',action='store_true')
    args=parser.parse_args()
    try:run(args.output,args.allow_hosted)
    except Exception as error:print(type(error).__name__+': '+str(error),file=sys.stderr);sys.exit(1)
