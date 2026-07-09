import os
import tempfile
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


def test_register_and_login_flow(client):
    register_resp = client.post('/api/auth/register', json={
        'email': 'test@example.com',
        'username': 'tester',
        'password': 'StrongPass123!',
        'agree_terms': True,
    })
    assert register_resp.status_code == 201

    login_resp = client.post('/api/auth/login', json={
        'identifier': 'test@example.com',
        'password': 'StrongPass123!',
        'remember_me': False,
    })
    assert login_resp.status_code == 200

    status_resp = client.get('/api/auth/status')
    assert status_resp.status_code == 200
    assert status_resp.get_json()['authenticated'] is True


def test_item_creation_and_listing(client):
    # register and login first
    client.post('/api/auth/register', json={
        'email': 'seller@example.com',
        'username': 'seller',
        'password': 'StrongPass123!',
        'agree_terms': True,
    })
    client.post('/api/auth/login', json={
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


def test_report_creation(client):
    client.post('/api/auth/register', json={
        'email': 'reporter@example.com',
        'username': 'reporter',
        'password': 'StrongPass123!',
        'agree_terms': True,
    })
    client.post('/api/auth/login', json={
        'identifier': 'reporter@example.com',
        'password': 'StrongPass123!',
    })

    report_resp = client.post('/api/reports', json={
        'target_type': 'item',
        'target_id': 1,
        'reason': 'fraud',
        'details': 'test report',
    })
    assert report_resp.status_code == 404
