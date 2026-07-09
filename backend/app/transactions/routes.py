from flask import request, jsonify
from app.transactions import transactions_bp
from app import db
from app.models import Transaction, Message
from flask_login import login_required, current_user


def _get_request_data():
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


@transactions_bp.route('/mine', methods=['GET'])
@login_required
def my_transactions():
    txs = Transaction.query.filter((Transaction.buyer_id == current_user.id) | (Transaction.seller_id == current_user.id)).order_by(Transaction.created_at.desc()).all()
    out = []
    for tx in txs:
        msgs = Message.query.filter_by(transaction_id=tx.id).order_by(Message.created_at.asc()).all()
        out.append({
            'id': tx.id,
            'item_id': tx.item_id,
            'buyer_id': tx.buyer_id,
            'seller_id': tx.seller_id,
            'status': tx.status,
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
        out.append({'id': m.id, 'sender_id': m.sender_id, 'content': m.content, 'created_at': m.created_at.isoformat()})
    return jsonify({'messages': out})


@transactions_bp.route('/<int:tx_id>/messages', methods=['POST'])
@login_required
def post_message(tx_id):
    tx = Transaction.query.get_or_404(tx_id)
    if current_user.id not in (tx.buyer_id, tx.seller_id):
        return jsonify({'error': 'forbidden'}), 403
    data = _get_request_data()
    content = data.get('content')
    if not content:
        return jsonify({'error': 'validation', 'message': 'empty content'}), 400
    msg = Message(transaction_id=tx.id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    return jsonify({'id': msg.id, 'content': msg.content, 'created_at': msg.created_at.isoformat()}), 201
