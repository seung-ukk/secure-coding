import bcrypt
from typing import BinaryIO
import imghdr

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
ALLOWED_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png'}
MAX_IMAGE_FILE_SIZE = 5 * 1024 * 1024


def verify_file_type(stream: BinaryIO) -> bool:
    # check image type by reading header
    head = stream.read(512)
    stream.seek(0)
    kind = imghdr.what(None, head)
    return kind in ('jpeg', 'png')


def detect_image_type(stream: BinaryIO) -> str | None:
    head = stream.read(512)
    stream.seek(0)
    return imghdr.what(None, head)


def is_allowed_image_extension(filename: str) -> bool:
    lowered = filename.lower()
    return any(lowered.endswith(ext) for ext in ALLOWED_IMAGE_EXTENSIONS)


def is_allowed_image_mime_type(mime_type: str | None) -> bool:
    return bool(mime_type and mime_type.lower() in ALLOWED_IMAGE_MIME_TYPES)


def get_file_size(stream: BinaryIO) -> int:
    current_position = stream.tell()
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(current_position)
    return size


def hash_password(password: str) -> str:
    pw = password.encode('utf-8')
    hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
    return hashed.decode('utf-8')


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False
