from decimal import Decimal, InvalidOperation
from flask import request, jsonify
from app.payments import payments_bp
from app import db
from app.models import User
from flask_login import login_required, current_user


@payments_bp.route('/transfer', methods=['POST'])
@login_required
def transfer():
    data = request.get_json() or {}
    to_user_id = data.get('to_user_id')
    amount = data.get('amount')
    if not to_user_id or amount is None:
        return jsonify({'error': 'validation'}), 400
    try:
        amt = Decimal(str(amount)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return jsonify({'error': 'validation', 'message': 'invalid amount'}), 400
    if amt <= 0:
        return jsonify({'error': 'validation', 'message': 'amount must be positive'}), 400
    if int(to_user_id) == current_user.id:
        return jsonify({'error': 'validation', 'message': 'cannot transfer to yourself'}), 400
    if not current_user.is_active:
        return jsonify({'error': 'forbidden', 'message': 'inactive users cannot transfer funds'}), 403
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'error': 'not_found'}), 404
    if not to_user.is_active:
        return jsonify({'error': 'validation', 'message': 'recipient account is inactive'}), 400
    if current_user.balance < amt:
        return jsonify({'error': 'validation', 'message': 'insufficient balance'}), 400

    current_user.balance -= amt
    to_user.balance += amt

    from app.models import AuditLog
    details = f"transfer {amt} from {current_user.id} to {to_user_id}"
    log = AuditLog(actor_id=current_user.id, action='transfer', target_type='user', target_id=to_user_id, details=details)
    db.session.add(log)
    db.session.commit()
    return jsonify({
        'transaction_id': log.id,
        'from_user_id': current_user.id,
        'to_user_id': int(to_user_id),
        'amount': float(amt),
        'from_balance': float(current_user.balance),
        'to_balance': float(to_user.balance),
        'status': 'completed',
    }), 201
