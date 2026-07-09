from flask import request, jsonify
from app.transactions import transactions_bp
from app import db
from app.models import Transaction, Message
from flask_login import login_required, current_user


@transactions_bp.route('/<int:tx_id>/messages', methods=['GET'])
@login_required
def get_messages(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        return jsonify({'error': 'forbidden'}), 403
    msgs = Message.query.filter_by(transaction_id=tx.id).order_by(Message.created_at.asc()).all()
    out = []
    for m in msgs:
        out.append({'id': m.id, 'sender_id': m.sender_id, 'content': m.content, 'created_at': m.created_at.isoformat()})
    return jsonify({'messages': out})


@transactions_bp.route('/<int:tx_id>/messages', methods=['POST'])
@login_required
def post_message(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json() or {}
    content = data.get('content')
    if not content:
        return jsonify({'error': 'validation', 'message': 'empty content'}), 400
    msg = Message(transaction_id=tx.id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'id': msg.id, 'content': msg.content, 'created_at': msg.created_at.isoformat()}), 201
