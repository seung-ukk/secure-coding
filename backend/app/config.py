import os
from datetime import timedelta


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f'{name} environment variable is required')
    return value


class Config:
    SECRET_KEY = require_env('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/secure_media')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    MAX_ITEM_IMAGE_COUNT = int(os.environ.get('MAX_ITEM_IMAGE_COUNT', '5'))
    MAX_ITEM_IMAGE_SIZE = int(os.environ.get('MAX_ITEM_IMAGE_SIZE', str(5 * 1024 * 1024)))
    AUTO_BLOCK_REPORT_THRESHOLD = int(os.environ.get('AUTO_BLOCK_REPORT_THRESHOLD', '5'))
    WTF_CSRF_ENABLED = os.environ.get('WTF_CSRF_ENABLED', 'true').lower() not in {'0', 'false', 'no', 'off'}
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.environ.get('SESSION_LIFETIME_MINUTES', '30')))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() in {'1', 'true', 'yes', 'on'}
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = os.environ.get('REMEMBER_COOKIE_SAMESITE', 'Lax')
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', 'false').lower() in {'1', 'true', 'yes', 'on'}
