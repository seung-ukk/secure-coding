from flask import request, jsonify, session
from app.auth import auth_bp
from app import db, login_manager
from app.models import User
from app.utils.security import hash_password, check_password
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf


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


@auth_bp.route('/register', methods=['POST'])
def register():
    data = _get_request_data()
    email = data.get('email')
    username = data.get('username')
    password = data.get('password')
    agree = _coerce_bool(data.get('agree_terms'))
    if not email or not username or not password or not agree:
        return jsonify({'error': 'validation', 'message': 'missing fields'}), 400
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
    identifier = data.get('identifier')
    password = data.get('password')
    remember = _coerce_bool(data.get('remember_me'))
    if not identifier or not password:
        return jsonify({'error': 'validation', 'message': 'missing credentials'}), 400
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({'error': 'unauthorized', 'message': 'invalid credentials'}), 401
    login_user(user, remember=remember)
    session.permanent = True
    return jsonify({'user': {'id': user.id, 'username': user.username, 'display_name': user.display_name}}), 200


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return ('', 204)


@auth_bp.route('/status', methods=['GET'])
def status():
    if current_user and current_user.is_authenticated:
        return jsonify({'authenticated': True, 'user': {'id': current_user.id, 'username': current_user.username}})
    return jsonify({'authenticated': False})


@auth_bp.route('/csrf-token', methods=['GET'])
def csrf_token():
    token = generate_csrf()
    return jsonify({'csrf_token': token})


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
