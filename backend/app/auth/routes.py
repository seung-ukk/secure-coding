from datetime import datetime, timedelta
import secrets
from flask import request, jsonify, session
from app.auth import auth_bp
from app import db, login_manager
from app.models import User
from app.utils.security import hash_password, check_password
from app.utils.validators import validate_email, validate_password, validate_username
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() not in {'', '0', 'false', 'no', 'off'}


def _is_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > datetime.utcnow())


def _remaining_lock_minutes(user: User) -> int:
    if not user.locked_until:
        return 0
    delta = user.locked_until - datetime.utcnow()
    return max(1, int(delta.total_seconds() // 60) + (1 if delta.total_seconds() % 60 else 0))


@auth_bp.route('/register', methods=['POST'])
def register():
    data = _get_request_data()
    email = (data.get('email') or '').strip().lower()
    username = (data.get('username') or '').strip()
    password = data.get('password')
    agree = _coerce_bool(data.get('agree_terms'))
    if not email or not username or not password or not agree:
        return jsonify({'error': 'validation', 'message': 'missing fields'}), 400
    if not validate_email(email):
        return jsonify({'error': 'validation', 'message': 'invalid email format'}), 400
    if not validate_username(username):
        return jsonify({'error': 'validation', 'message': 'username must be 3-30 chars using letters, numbers, or underscore'}), 400
    if not validate_password(password):
        return jsonify({
            'error': 'validation',
            'message': 'password must be at least 8 chars and include uppercase, lowercase, number, and special character',
        }), 400
    # duplicate check
    if User.query.filter((User.email == email) | (User.username == username)).first():
        return jsonify({'error': 'conflict', 'message': 'email or username exists'}), 409
    hashed = hash_password(password)
    user = User(email=email, username=username, password_hash=hashed, display_name=username)
    db.session.add(user)
    db.session.commit()
    return jsonify({'id': user.id, 'email': user.email, 'username': user.username, 'created_at': user.created_at.isoformat()}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = _get_request_data()
    identifier = (data.get('identifier') or '').strip()
    password = data.get('password')
    remember = _coerce_bool(data.get('remember_me'))
    if not identifier or not password:
        return jsonify({'error': 'validation', 'message': 'missing credentials'}), 400
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    if not user:
        return jsonify({'error': 'unauthorized', 'message': 'invalid credentials'}), 401
    if not user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'account is inactive'}), 403
    if _is_locked(user):
        return jsonify({
            'error': 'locked',
            'message': f'too many failed attempts; try again in {_remaining_lock_minutes(user)} minute(s)',
        }), 423
    if not check_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_count = 0
        db.session.commit()
        return jsonify({'error': 'unauthorized', 'message': 'invalid credentials'}), 401
    user.failed_login_count = 0
    user.locked_until = None
    session_token = secrets.token_hex(32)
    user.active_session_token = session_token
    db.session.commit()
    session.clear()
    login_user(user, remember=remember)
    session['session_version'] = user.session_version
    session['session_token'] = session_token
    session.permanent = True
    return jsonify({'user': {'id': user.id, 'username': user.username, 'display_name': user.display_name}}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    if current_user.is_authenticated and session.get('session_token') == current_user.active_session_token:
        current_user.active_session_token = None
        db.session.commit()
    session.clear()
    logout_user()
    return ('', 204)


@auth_bp.route('/status', methods=['GET'])
def status():
    if current_user and current_user.is_authenticated:
        return jsonify({'authenticated': True, 'user': {'id': current_user.id, 'username': current_user.username, 'role': current_user.role}})
    return jsonify({'authenticated': False})


@auth_bp.route('/csrf-token', methods=['GET'])
def csrf_token():
    token = generate_csrf()
    return jsonify({'csrf_token': token})


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
