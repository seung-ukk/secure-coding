from flask import request, jsonify, abort
from app.users import users_bp
from app import db
from app.models import User, Item
from flask_login import login_required, current_user, logout_user
from app.utils.security import hash_password, check_password
from app.utils.validators import validate_password

def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_active:
        return jsonify({'error': 'inactive_user', 'message': 'User account is inactive'}), 400

    # Query public items registered by this user
    items = Item.query.filter_by(owner_id=user.id).filter(Item.status.notin_({'deleted', 'blocked'})).all()
    
    return jsonify({
        'username': user.username,
        'display_name': user.display_name,
        'bio': user.bio,
        'created_at': user.created_at.isoformat(),
        'is_active': user.is_active,
        'items': [{'id': it.id, 'title': it.title, 'price': float(it.price), 'status': it.status} for it in items]
    }), 200


@users_bp.route('/me', methods=['GET'])
@login_required
def get_my_profile():
    return jsonify({
        'id': current_user.id,
        'email': current_user.email,
        'username': current_user.username,
        'display_name': current_user.display_name,
        'bio': current_user.bio,
        'is_active': current_user.is_active,
        'role': current_user.role,
        'balance': float(current_user.balance),
        'created_at': current_user.created_at.isoformat()
    }), 200


@users_bp.route('/me/profile', methods=['PATCH'])
@login_required
def update_profile():
    data = _get_request_data()
    display_name = data.get('display_name')
    bio = data.get('bio')
    
    if display_name is not None:
        display_name = display_name.strip()
        if not (1 <= len(display_name) <= 50):
            return jsonify({'error': 'validation', 'message': 'Display name must be between 1 and 50 characters'}), 400
        current_user.display_name = display_name
        
    if bio is not None:
        bio = bio.strip()
        if len(bio) > 500:
            return jsonify({'error': 'validation', 'message': 'Bio must not exceed 500 characters'}), 400
        current_user.bio = bio
        
    db.session.commit()
    
    return jsonify({
        'display_name': current_user.display_name,
        'bio': current_user.bio
    }), 200


@users_bp.route('/me/password', methods=['PATCH'])
@login_required
def update_password():
    data = _get_request_data()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    new_password_confirm = data.get('new_password_confirm')
    
    if not current_password or not new_password or not new_password_confirm:
        return jsonify({'error': 'validation', 'message': 'All fields are required'}), 400
        
    if not check_password(current_password, current_user.password_hash):
        return jsonify({'error': 'unauthorized', 'message': 'Invalid current password'}), 401
        
    if new_password != new_password_confirm:
        return jsonify({'error': 'validation', 'message': 'New passwords do not match'}), 400
        
    if current_password == new_password:
        return jsonify({'error': 'validation', 'message': 'New password must be different from current password'}), 400
        
    if not validate_password(new_password):
        return jsonify({
            'error': 'validation', 
            'message': 'Password must be at least 8 characters long, and contain at least one uppercase letter, one lowercase letter, one number, and one special character'
        }), 400
        
    current_user.password_hash = hash_password(new_password)
    current_user.session_version += 1
    current_user.active_session_token = None
    db.session.commit()
    
    logout_user()
    
    return jsonify({'status': 'success', 'message': 'Password updated successfully. Please login again.'}), 200
