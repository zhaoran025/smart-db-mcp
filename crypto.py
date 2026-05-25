from cryptography.fernet import Fernet
from config import KEY_FILE


def _get_or_create_key() -> bytes:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


_fernet = Fernet(_get_or_create_key())


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(cipher: str) -> str:
    return _fernet.decrypt(cipher.encode()).decode()
