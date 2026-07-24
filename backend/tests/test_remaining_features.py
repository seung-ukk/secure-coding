from app import db
from app.models import User


def register_and_login(client, email: str, username: str, password: str = 'StrongPass123!'):
    client.post('/api/auth/register', data={
        'email': email,
        'username': username,
        'password': password,
        'agree_terms': 'on',
    })
    return client.post('/api/auth/login', data={
        'identifier': email,
        'password': password,
    })


def promote_admin(app, username: str, balance: float | None = None):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.role = 'admin'
        if balance is not None:
            user.balance = balance
        db.session.commit()


def set_balance(app, username: str, balance: float):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.balance = balance
        db.session.commit()


def test_chat_room_endpoints(client):
    register_and_login(client, 'seller-chat@example.com', 'sellerchat')
    create_item = client.post('/api/items', data={
        'title': 'Chat Item',
        'description': 'Item for room creation',
        'price': '12000',
    })
    item_id = create_item.get_json()['id']
    client.post('/api/auth/logout')

    register_and_login(client, 'buyer-chat@example.com', 'buyerchat')
    room_resp = client.post('/api/chat/rooms', json={'item_id': item_id})
    assert room_resp.status_code == 201
    room_id = room_resp.get_json()['id']

    get_room = client.get(f'/api/chat/rooms/{room_id}')
    assert get_room.status_code == 200
    assert get_room.get_json()['item_id'] == item_id

    post_msg = client.post(f'/api/chat/rooms/{room_id}/messages', json={'content': 'hello room'})
    assert post_msg.status_code == 201

    get_msgs = client.get(f'/api/chat/rooms/{room_id}/messages')
    assert get_msgs.status_code == 200
    assert get_msgs.get_json()['messages'][-1]['content'] == 'hello room'


def test_admin_can_manage_report_threshold_and_read_audit_logs(client, app):
    register_and_login(client, 'admin-threshold@example.com', 'adminthreshold')
    client.post('/api/auth/logout')
    promote_admin(app, 'adminthreshold')
    register_and_login(client, 'admin-threshold@example.com', 'adminthreshold')

    get_threshold = client.get('/api/admin/settings/report-threshold')
    assert get_threshold.status_code == 200

    patch_threshold = client.patch('/api/admin/settings/report-threshold', json={'report_threshold': 2})
    assert patch_threshold.status_code == 200
    assert patch_threshold.get_json()['report_threshold'] == 2

    logs = client.get('/api/admin/audit-logs')
    assert logs.status_code == 200
    assert any(log['action'] == 'admin_update_report_threshold' for log in logs.get_json()['logs'])


def test_admin_deactivation_blocks_future_login(client, app):
    victim_client = app.test_client()
    admin_client = app.test_client()

    register_and_login(victim_client, 'victim-session@example.com', 'victimsession')
    protected_before = victim_client.get('/api/me')
    assert protected_before.status_code == 200

    register_and_login(admin_client, 'admin-session@example.com', 'adminsession')
    admin_client.post('/api/auth/logout')
    promote_admin(app, 'adminsession')
    register_and_login(admin_client, 'admin-session@example.com', 'adminsession')
    target_id = None
    with app.app_context():
        target = User.query.filter_by(username='victimsession').first()
        target_id = target.id
    deactivate = admin_client.patch(f'/api/admin/users/{target_id}/status', json={'is_active': False})
    assert deactivate.status_code == 200

    with app.app_context():
        target = db.session.get(User, target_id, populate_existing=True)
        assert target.is_active is False
        assert target.session_version >= 1

    blocked_login_client = app.test_client()
    blocked_login = blocked_login_client.post('/api/auth/login', data={
        'identifier': 'victim-session@example.com',
        'password': 'StrongPass123!',
    })
    assert blocked_login.status_code == 403


def test_new_login_invalidates_previous_session(app):
    first_client = app.test_client()
    second_client = app.test_client()

    register_and_login(first_client, 'session-user@example.com', 'sessionuser')
    assert first_client.get('/api/me').status_code == 200

    register_and_login(second_client, 'session-user@example.com', 'sessionuser')
    assert second_client.get('/api/me').status_code == 200

    expired = first_client.get('/api/me')
    assert expired.status_code == 401


def test_transaction_status_flow_updates_item_status(client):
    register_and_login(client, 'seller-flow@example.com', 'sellerflow')
    create_item = client.post('/api/items', data={
        'title': 'Flow Item',
        'description': 'Item for transaction state flow',
        'price': '23000',
    })
    item_id = create_item.get_json()['id']
    client.post('/api/auth/logout')

    buyer_client = client.application.test_client()
    register_and_login(buyer_client, 'buyer-flow@example.com', 'buyerflow')
    request_resp = buyer_client.post(f'/api/items/{item_id}/request')
    assert request_resp.status_code == 201
    tx_id = request_resp.get_json()['transaction_id']
    client.post('/api/auth/logout')

    seller_client = client.application.test_client()
    register_and_login(seller_client, 'seller-flow@example.com', 'sellerflow')
    accept_resp = seller_client.patch(f'/api/transactions/{tx_id}/status', json={'action': 'accept'})
    assert accept_resp.status_code == 200
    assert accept_resp.get_json()['transaction']['status'] == 'accepted'
    assert accept_resp.get_json()['item_status'] == 'reserved'

    complete_resp = seller_client.patch(f'/api/transactions/{tx_id}/status', json={'action': 'complete'})
    assert complete_resp.status_code == 200
    assert complete_resp.get_json()['transaction']['status'] == 'completed'
    assert complete_resp.get_json()['item_status'] == 'sold'

    buyer_retry_client = client.application.test_client()
    register_and_login(buyer_retry_client, 'buyer-flow@example.com', 'buyerflow')
    sold_request = buyer_retry_client.post(f'/api/items/{item_id}/request')
    assert sold_request.status_code == 400


def test_buyer_cancel_returns_item_to_available(client):
    register_and_login(client, 'seller-cancel@example.com', 'sellercancel')
    create_item = client.post('/api/items', data={
        'title': 'Cancelable Item',
        'description': 'Item for cancel flow',
        'price': '18000',
    })
    item_id = create_item.get_json()['id']
    client.post('/api/auth/logout')

    buyer_client = client.application.test_client()
    register_and_login(buyer_client, 'buyer-cancel@example.com', 'buyercancel')
    request_resp = buyer_client.post(f'/api/items/{item_id}/request')
    tx_id = request_resp.get_json()['transaction_id']

    seller_client = client.application.test_client()
    register_and_login(seller_client, 'seller-cancel@example.com', 'sellercancel')
    seller_client.patch(f'/api/transactions/{tx_id}/status', json={'action': 'accept'})

    buyer_retry_client = client.application.test_client()
    register_and_login(buyer_retry_client, 'buyer-cancel@example.com', 'buyercancel')
    cancel_resp = buyer_retry_client.patch(f'/api/transactions/{tx_id}/status', json={'action': 'cancel'})
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json()['transaction']['status'] == 'cancelled'
    assert cancel_resp.get_json()['item_status'] == 'available'


def test_payment_transfer_updates_balances(client, app):
    register_and_login(client, 'sender@example.com', 'sender')
    client.post('/api/auth/logout')
    register_and_login(client, 'receiver@example.com', 'receiver')
    client.post('/api/auth/logout')

    set_balance(app, 'sender', 100000)
    set_balance(app, 'receiver', 5000)

    register_and_login(client, 'sender@example.com', 'sender')
    with app.app_context():
        receiver = User.query.filter_by(username='receiver').first()
        receiver_id = receiver.id

    transfer = client.post('/api/payments/transfer', json={
        'to_user_id': receiver_id,
        'amount': '25000',
    })
    assert transfer.status_code == 201
    payload = transfer.get_json()
    assert payload['from_balance'] == 75000.0
    assert payload['to_balance'] == 30000.0
