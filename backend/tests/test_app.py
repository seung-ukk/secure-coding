import os
import tempfile
from pathlib import Path
import pytest
from app import create_app, db


@pytest.fixture()
def app():
    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret',
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        UPLOAD_FOLDER=tempfile.mkdtemp(),
        WTF_CSRF_ENABLED=False,
    )
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_core_pages_render(client):
    for path in ['/', '/login', '/register', '/items']:
        response = client.get(path)
        assert response.status_code == 200


def test_authenticated_home_page_shows_personalized_content(client):
    client.post('/api/auth/register', data={
        'email': 'homeuser@example.com',
        'username': 'homeuser',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'homeuser@example.com',
        'password': 'StrongPass123!',
    })

    response = client.get('/')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'homeuser' in body
    assert '상품 조회' in body


def test_items_pages_include_interactive_actions(client):
    items_page = client.get('/items')
    assert items_page.status_code == 200
    assert '판매글 등록'.encode('utf-8') in items_page.data
    assert 'name="title"'.encode('utf-8') in items_page.data
    assert 'name="price"'.encode('utf-8') in items_page.data

    detail_page = client.get('/items/1')
    assert detail_page.status_code == 200
    assert '구매 요청'.encode('utf-8') in detail_page.data


def test_register_works_on_fresh_app_startup():
    db_path = Path('app.db')
    if db_path.exists():
        db_path.unlink()

    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY='test-secret',
        WTF_CSRF_ENABLED=False,
    )
    with app.test_client() as client:
        response = client.post('/api/auth/register', data={
            'email': 'fresh@example.com',
            'username': 'fresh',
            'password': 'StrongPass123!',
            'agree_terms': 'on',
        })
        assert response.status_code == 201


def test_register_and_login_flow(client):
    register_resp = client.post('/api/auth/register', data={
        'email': 'test@example.com',
        'username': 'tester',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    assert register_resp.status_code == 201

    login_resp = client.post('/api/auth/login', data={
        'identifier': 'test@example.com',
        'password': 'StrongPass123!',
        'remember_me': 'false',
    })
    assert login_resp.status_code == 200

    status_resp = client.get('/api/auth/status')
    assert status_resp.status_code == 200
    assert status_resp.get_json()['authenticated'] is True


def test_item_creation_and_listing(client):
    # register and login first
    client.post('/api/auth/register', data={
        'email': 'seller@example.com',
        'username': 'seller',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'seller@example.com',
        'password': 'StrongPass123!',
    })

    create_resp = client.post('/api/items', data={
        'title': '책상',
        'description': '좋은 책상',
        'price': '50000',
        'category_id': '1',
    })
    assert create_resp.status_code == 201

    list_resp = client.get('/api/items')
    assert list_resp.status_code == 200
    payload = list_resp.get_json()
    assert payload['total'] >= 1
    assert any(item['title'] == '책상' for item in payload['items'])


def test_dashboard_api_for_authenticated_user(client):
    client.post('/api/auth/register', data={
        'email': 'dashboard@example.com',
        'username': 'dashboard',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'dashboard@example.com',
        'password': 'StrongPass123!',
    })

    create_resp = client.post('/api/items', data={
        'title': '의자',
        'description': '좋은 의자',
        'price': '40000',
    })
    assert create_resp.status_code == 201

    my_items_resp = client.get('/api/items/mine')
    assert my_items_resp.status_code == 200
    assert my_items_resp.get_json()['items'][0]['title'] == '의자'

    my_transactions_resp = client.get('/api/transactions/mine')
    assert my_transactions_resp.status_code == 200


def test_dashboard_includes_messages(client):
    client.post('/api/auth/register', data={
        'email': 'msguser@example.com',
        'username': 'msguser',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'msguser@example.com',
        'password': 'StrongPass123!',
    })

    create_item_resp = client.post('/api/items', data={
        'title': '책장',
        'description': '좋은 책장',
        'price': '30000',
    })
    assert create_item_resp.status_code == 201

    my_items_resp = client.get('/api/items/mine')
    assert my_items_resp.status_code == 200

    my_transactions_resp = client.get('/api/transactions/mine')
    assert my_transactions_resp.status_code == 200
    payload = my_transactions_resp.get_json()
    assert isinstance(payload['transactions'], list)


def test_purchase_request_message_and_report_flow(client):
    client.post('/api/auth/register', data={
        'email': 'seller2@example.com',
        'username': 'seller2',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'seller2@example.com',
        'password': 'StrongPass123!',
    })

    create_item_resp = client.post('/api/items', data={
        'title': '노트북',
        'description': '좋은 노트북',
        'price': '100000',
    })
    assert create_item_resp.status_code == 201
    item_id = create_item_resp.get_json()['id']

    logout_resp = client.post('/api/auth/logout')
    assert logout_resp.status_code == 204

    client.post('/api/auth/register', data={
        'email': 'buyer@example.com',
        'username': 'buyer',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'buyer@example.com',
        'password': 'StrongPass123!',
    })

    request_resp = client.post(f'/api/items/{item_id}/request')
    assert request_resp.status_code == 201
    transaction_id = request_resp.get_json()['transaction_id']

    message_resp = client.post(f'/api/transactions/{transaction_id}/messages', json={
        'content': '구매 가능할까요?'
    })
    assert message_resp.status_code == 201

    report_resp = client.post('/api/reports', json={
        'target_type': 'item',
        'target_id': item_id,
        'reason': 'fraud',
        'details': 'test report',
    })
    assert report_resp.status_code == 201
