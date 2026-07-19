from flask import request, jsonify, abort
from app.chat import chat_bp
from app import db
from app.models import GlobalMessage, User
from flask_login import login_required, current_user
from markupsafe import escape

def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


@chat_bp.route('/global/messages', methods=['GET'])
@login_required
def get_global_messages():
    # Query global active messages
    msgs = (db.session.query(GlobalMessage, User)
            .join(User, GlobalMessage.sender_id == User.id)
            .filter(GlobalMessage.status == 'active')
            .order_by(GlobalMessage.created_at.asc())
            .all())
            
    out = []
    for msg, user in msgs:
        out.append({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'username': user.username,
            'display_name': user.display_name,
            'content': str(escape(msg.content)),
            'created_at': msg.created_at.isoformat()
        })
        
    return jsonify({'messages': out}), 200


@chat_bp.route('/global/messages', methods=['POST'])
@login_required
def post_global_message():
    # Restrict inactive / dormant users from posting
    if not current_user.is_active:
        return jsonify({'error': 'unauthorized', 'message': 'Inactive or dormant users cannot send messages'}), 403
        
    data = _get_request_data()
    content = data.get('content')
    if not content:
        return jsonify({'error': 'validation', 'message': 'Message content is required'}), 400
        
    content = content.strip()
    if len(content) > 1000:
        return jsonify({'error': 'validation', 'message': 'Message content cannot exceed 1000 characters'}), 400
        
    msg = GlobalMessage(sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({
        'id': msg.id,
        'content': str(escape(msg.content)),
        'created_at': msg.created_at.isoformat()
    }), 201
