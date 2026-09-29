"""Password hashing; raw bearer tokens exist only in requests and responses."""
from pwdlib import PasswordHash

PASSWORD_HASH = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return PASSWORD_HASH.verify(password, encoded)
