from datetime import datetime, timedelta
from flask import request, jsonify
from app.transactions import transactions_bp
from app import db
from app.models import Transaction, Message, Item, AuditLog
from flask_login import login_required, current_user
from markupsafe import escape

MAX_DIRECT_MESSAGE_LENGTH = 1000
DIRECT_MESSAGE_RATE_LIMIT_COUNT = 5
DIRECT_MESSAGE_RATE_LIMIT_WINDOW_SECONDS = 30
ACTIVE_TRANSACTION_STATUSES = {'requested', 'accepted'}
SELLER_ACTIONS = {'accept', 'decline', 'complete'}
BUYER_ACTIONS = {'cancel'}


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
    if len(normalized) > MAX_DIRECT_MESSAGE_LENGTH:
        return False, f'message content cannot exceed {MAX_DIRECT_MESSAGE_LENGTH} characters', None
    return True, '', normalized


def _is_rate_limited(sender_id: int) -> bool:
    window_start = datetime.utcnow() - timedelta(seconds=DIRECT_MESSAGE_RATE_LIMIT_WINDOW_SECONDS)
    recent_count = Message.query.filter(
        Message.sender_id == sender_id,
        Message.created_at >= window_start,
    ).count()
    return recent_count >= DIRECT_MESSAGE_RATE_LIMIT_COUNT


def _serialize_transaction(tx: Transaction):
    return {
        'id': tx.id,
        'item_id': tx.item_id,
        'buyer_id': tx.buyer_id,
        'seller_id': tx.seller_id,
        'status': tx.status,
        'created_at': tx.created_at.isoformat(),
        'updated_at': tx.updated_at.isoformat() if tx.updated_at else None,
    }


def _refresh_item_status(item_id: int):
    item = Item.query.get_or_404(item_id)
    accepted_exists = Transaction.query.filter_by(item_id=item.id, status='accepted').first() is not None
    completed_exists = Transaction.query.filter_by(item_id=item.id, status='completed').first() is not None

    if item.status in ('deleted', 'blocked'):
        return item
    if completed_exists:
        item.status = 'sold'
    elif accepted_exists:
        item.status = 'reserved'
    else:
        item.status = 'available'
    return item


@transactions_bp.route('/mine', methods=['GET'])
@login_required
def my_transactions():
    txs = Transaction.query.filter((Transaction.buyer_id == current_user.id) | (Transaction.seller_id == current_user.id)).order_by(Transaction.created_at.desc()).all()
    out = []
    for tx in txs:
        msgs = Message.query.filter_by(transaction_id=tx.id).order_by(Message.created_at.asc()).all()
        out.append({
            **_serialize_transaction(tx),
            'messages': [{'id': m.id, 'sender_id': m.sender_id, 'content': m.content} for m in msgs],
        })
    return jsonify({'transactions': out})


@transactions_bp.route('/<int:tx_id>/messages', methods=['GET'])
@login_required
def get_messages(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        return jsonify({'error': 'forbidden'}), 403
    msgs = Message.query.filter_by(transaction_id=tx.id).order_by(Message.created_at.asc()).all()
    out = []
    for m in msgs:
        out.append({'id': m.id, 'sender_id': m.sender_id, 'content': str(escape(m.content)), 'created_at': m.created_at.isoformat()})
    return jsonify({'messages': out})


@transactions_bp.route('/<int:tx_id>/messages', methods=['POST'])
@login_required
def post_message(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        return jsonify({'error': 'forbidden'}), 403
    if not current_user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'inactive users cannot send messages'}), 403
    if tx.status not in {'requested', 'accepted'}:
        return jsonify({'error': 'validation', 'message': 'messages are only allowed for active transactions'}), 400
    data = _get_request_data()
    content_ok, message, content = _normalize_message_content(data.get('content'))
    if not content_ok:
        return jsonify({'error': 'validation', 'message': message}), 400
    if _is_rate_limited(current_user.id):
        return jsonify({'error': 'rate_limited', 'message': 'too many messages sent; try again later'}), 429
    msg = Message(transaction_id=tx.id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'id': msg.id, 'content': str(escape(msg.content)), 'created_at': msg.created_at.isoformat()}), 201


@transactions_bp.route('/<int:tx_id>/status', methods=['PATCH'])
@login_required
def update_transaction_status(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    item = Item.query.get_or_404(tx.item_id)
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip().lower()
    if not action:
        return jsonify({'error': 'validation', 'message': 'action is required'}), 400

    actor_role = None
    if current_user.id == tx.seller_id:
        actor_role = 'seller'
    elif current_user.id == tx.buyer_id:
        actor_role = 'buyer'
    else:
        return jsonify({'error': 'forbidden', 'message': 'you are not part of this transaction'}), 403

    if actor_role == 'seller' and action not in SELLER_ACTIONS:
        return jsonify({'error': 'forbidden', 'message': 'seller cannot perform this action'}), 403
    if actor_role == 'buyer' and action not in BUYER_ACTIONS:
        return jsonify({'error': 'forbidden', 'message': 'buyer cannot perform this action'}), 403

    if action == 'accept':
        if tx.status != 'requested':
            return jsonify({'error': 'validation', 'message': 'only requested transactions can be accepted'}), 400
        if item.status != 'available':
            return jsonify({'error': 'validation', 'message': 'item is not available'}), 400
        other_accepted = Transaction.query.filter(
            Transaction.item_id == item.id,
            Transaction.id != tx.id,
            Transaction.status == 'accepted',
        ).first()
        if other_accepted:
            return jsonify({'error': 'validation', 'message': 'another accepted transaction already exists'}), 400
        tx.status = 'accepted'
    elif action == 'decline':
        if tx.status != 'requested':
            return jsonify({'error': 'validation', 'message': 'only requested transactions can be declined'}), 400
        tx.status = 'declined'
    elif action == 'cancel':
        if tx.status not in {'requested', 'accepted'}:
            return jsonify({'error': 'validation', 'message': 'only active transactions can be cancelled'}), 400
        tx.status = 'cancelled'
    elif action == 'complete':
        if tx.status != 'accepted':
            return jsonify({'error': 'validation', 'message': 'only accepted transactions can be completed'}), 400
        tx.status = 'completed'

    _refresh_item_status(item.id)
    log = AuditLog(
        actor_id=current_user.id,
        action='transaction_status_update',
        target_type='transaction',
        target_id=tx.id,
        details=f'{actor_role} performed {action} on transaction {tx.id}',
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({
        'transaction': _serialize_transaction(tx),
        'item_status': item.status,
    }), 200
