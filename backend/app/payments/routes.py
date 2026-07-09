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
        amt = float(amount)
    except Exception:
        return jsonify({'error': 'validation', 'message': 'invalid amount'}), 400
    if amt <= 0:
        return jsonify({'error': 'validation', 'message': 'amount must be positive'}), 400
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'error': 'not_found'}), 404
    # For prototype: use simple balances on User model via audit logs
    # In real app have balances table and atomic DB transactions
    # Record audit
    from app.models import AuditLog
    details = f"transfer {amt} from {current_user.id} to {to_user_id}"
    log = AuditLog(actor_id=current_user.id, action='transfer', target_type='user', target_id=to_user_id, details=details)
    db.session.add(log)
    db.session.commit()
    return jsonify({'transaction_id': log.id, 'from_user_id': current_user.id, 'to_user_id': to_user_id, 'amount': amt, 'status': 'completed'}), 201
