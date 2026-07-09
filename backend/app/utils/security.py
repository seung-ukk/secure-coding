import bcrypt
from werkzeug.datastructures import FileStorage
from typing import BinaryIO
import imghdr
import io


def verify_file_type(stream: BinaryIO) -> bool:
    # check image type by reading header
    head = stream.read(512)
    stream.seek(0)
    kind = imghdr.what(None, head)
    return kind in ('jpeg', 'png')


def hash_password(password: str) -> str:
    pw = password.encode('utf-8')
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode('utf-8')


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False
