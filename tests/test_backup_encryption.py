import importlib.util,unittest,os
from pathlib import Path
from cryptography.exceptions import InvalidTag
spec=importlib.util.spec_from_file_location('backup_database',Path(__file__).resolve().parents[1]/'scripts/backup_database.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class BackupEncryptionTests(unittest.TestCase):
    def test_encrypt_authenticate_and_reject_modified_or_wrong_key(self):
        data=b'SYNTHETIC PostgreSQL dump';key=os.urandom(32);encrypted=module.encrypt(data,key)
        self.assertNotIn(data,encrypted);self.assertEqual(module.decrypt(encrypted,key),data)
        with self.assertRaises(InvalidTag):module.decrypt(encrypted,os.urandom(32))
        with self.assertRaises(InvalidTag):module.decrypt(encrypted[:-1]+bytes([encrypted[-1]^1]),key)
