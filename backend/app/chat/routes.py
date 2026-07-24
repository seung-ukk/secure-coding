from datetime import datetime, timedelta
from flask import request, jsonify, abort
from app.chat import chat_bp
from app import db
from app.models import GlobalMessage, User, Item, Transaction, Message
from flask_login import login_required, current_user
from markupsafe import escape

MAX_CHAT_MESSAGE_LENGTH = 1000
CHAT_RATE_LIMIT_COUNT = 5
CHAT_RATE_LIMIT_WINDOW_SECONDS = 30

def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def _normalize_message_content(content: str | None):
    if content is None:
        return False, 'message content is required', None
    normalized = content.strip()
    if not normalized:
        return False, 'message content is required', None
    if len(normalized) > MAX_CHAT_MESSAGE_LENGTH:
        return False, f'message content cannot exceed {MAX_CHAT_MESSAGE_LENGTH} characters', None
    return True, '', normalized


def _is_rate_limited(model, sender_id: int) -> bool:
    window_start = datetime.utcnow() - timedelta(seconds=CHAT_RATE_LIMIT_WINDOW_SECONDS)
    recent_count = model.query.filter(
        model.sender_id == sender_id,
        model.created_at >= window_start,
    ).count()
    return recent_count >= CHAT_RATE_LIMIT_COUNT


def _serialize_room(room: Transaction):
    return {
        'id': room.id,
        'item_id': room.item_id,
        'buyer_id': room.buyer_id,
        'seller_id': room.seller_id,
        'status': room.status,
        'created_at': room.created_at.isoformat(),
    }


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
    content_ok, message, content = _normalize_message_content(data.get('content'))
    if not content_ok:
        return jsonify({'error': 'validation', 'message': message}), 400
    if _is_rate_limited(GlobalMessage, current_user.id):
        return jsonify({'error': 'rate_limited', 'message': 'too many messages sent; try again later'}), 429

    msg = GlobalMessage(sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({
        'id': msg.id,
        'content': str(escape(msg.content)),
        'created_at': msg.created_at.isoformat()
    }), 201


@chat_bp.route('/rooms', methods=['POST'])
@login_required
def create_chat_room():
    if not current_user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'inactive users cannot create chat rooms'}), 403

    data = _get_request_data()
    item_id = data.get('item_id')
    if not item_id:
        return jsonify({'error': 'validation', 'message': 'item_id is required'}), 400

    item = Item.query.get_or_404(item_id)
    if item.owner_id == current_user.id:
        return jsonify({'error': 'validation', 'message': 'cannot create a room for your own item'}), 400
    if item.status != 'available':
        return jsonify({'error': 'validation', 'message': 'cannot create a room for this item'}), 400

    room = Transaction.query.filter_by(
        item_id=item.id,
        buyer_id=current_user.id,
        seller_id=item.owner_id,
    ).filter(Transaction.status.in_(['requested', 'accepted'])).order_by(Transaction.created_at.desc()).first()
    created = False
    if not room:
        room = Transaction(item_id=item.id, buyer_id=current_user.id, seller_id=item.owner_id)
        db.session.add(room)
        db.session.commit()
        created = True
    return jsonify(_serialize_room(room)), 201 if created else 200


@chat_bp.route('/rooms/<int:room_id>', methods=['GET'])
@login_required
def get_chat_room(room_id):
    room = Transaction.query.get_or_404(room_id)
    if current_user.id not in (room.buyer_id, room.seller_id):
        return jsonify({'error': 'forbidden', 'message': 'you are not a participant in this room'}), 403
    return jsonify(_serialize_room(room)), 200


@chat_bp.route('/rooms/<int:room_id>/messages', methods=['GET'])
@login_required
def get_chat_room_messages(room_id):
    room = Transaction.query.get_or_404(room_id)
    if current_user.id not in (room.buyer_id, room.seller_id):
        return jsonify({'error': 'forbidden', 'message': 'you are not a participant in this room'}), 403

    messages = Message.query.filter_by(transaction_id=room.id).order_by(Message.created_at.asc()).all()
    return jsonify({
        'messages': [
            {
                'id': message.id,
                'sender_id': message.sender_id,
                'content': str(escape(message.content)),
                'created_at': message.created_at.isoformat(),
            }
            for message in messages
        ]
    }), 200


@chat_bp.route('/rooms/<int:room_id>/messages', methods=['POST'])
@login_required
def post_chat_room_message(room_id):
    room = Transaction.query.get_or_404(room_id)
    if current_user.id not in (room.buyer_id, room.seller_id):
        return jsonify({'error': 'forbidden', 'message': 'you are not a participant in this room'}), 403
    if not current_user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'inactive users cannot send messages'}), 403

    data = _get_request_data()
    content_ok, message, content = _normalize_message_content(data.get('content'))
    if not content_ok:
        return jsonify({'error': 'validation', 'message': message}), 400
    if _is_rate_limited(Message, current_user.id):
        return jsonify({'error': 'rate_limited', 'message': 'too many messages sent; try again later'}), 429

    msg = Message(transaction_id=room.id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({
        'id': msg.id,
        'content': str(escape(msg.content)),
        'created_at': msg.created_at.isoformat(),
    }), 201
