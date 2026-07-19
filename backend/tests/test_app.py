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


def test_admin_authorization(client, app):
    # 1. Unauthenticated request should be forbidden
    resp = client.get('/api/admin/reports')
    assert resp.status_code == 403

    # 2. Authenticated as non-admin ('user') should be forbidden
    client.post('/api/auth/register', data={
        'email': 'user1@example.com',
        'username': 'user1',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'user1@example.com',
        'password': 'StrongPass123!',
    })
    resp = client.get('/api/admin/reports')
    assert resp.status_code == 403

    # Logout
    client.post('/api/auth/logout')

    # 3. Authenticated as admin ('admin') should be authorized
    client.post('/api/auth/register', data={
        'email': 'admin1@example.com',
        'username': 'admin1',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })

    with app.app_context():
        from app.models import User
        from app import db
        admin_user = User.query.filter_by(username='admin1').first()
        admin_user.role = 'admin'
        db.session.commit()

    client.post('/api/auth/login', data={
        'identifier': 'admin1@example.com',
        'password': 'StrongPass123!',
    })

    resp = client.get('/api/admin/reports')
    assert resp.status_code == 200
    assert 'reports' in resp.get_json()


def test_csrf_protection_enabled_by_default():
    from app import create_app
    default_app = create_app()
    assert default_app.config['WTF_CSRF_ENABLED'] is True


def test_csrf_blocks_post_requests_without_token(app):
    app.config['WTF_CSRF_ENABLED'] = True
    with app.test_client() as client:
        response = client.post('/api/auth/register', data={
            'email': 'csrf@example.com',
            'username': 'csrfuser',
            'password': 'StrongPass123!',
            'agree_terms': 'on',
        })
        assert response.status_code == 400


def test_csrf_allows_post_requests_with_token(app):
    app.config['WTF_CSRF_ENABLED'] = True
    with app.test_client() as client:
        token_resp = client.get('/api/auth/csrf-token')
        assert token_resp.status_code == 200
        csrf_token = token_resp.get_json()['csrf_token']

        response = client.post('/api/auth/register', data={
            'email': 'csrf2@example.com',
            'username': 'csrfuser2',
            'password': 'StrongPass123!',
            'agree_terms': 'on',
        }, headers={'X-CSRFToken': csrf_token})
        assert response.status_code == 201


def test_item_creation_with_image_and_serving(client, app):
    client.post('/api/auth/register', data={
        'email': 'uploader@example.com',
        'username': 'uploader',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'uploader@example.com',
        'password': 'StrongPass123!',
    })

    import io
    # Valid minimal PNG header and structure to pass verify_file_type (imghdr checks magic bytes)
    dummy_image = (io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'), 'test.png')

    create_resp = client.post('/api/items', data={
        'title': '카메라',
        'description': '빈티지 카메라',
        'price': '150000',
        'images[]': dummy_image,
    }, content_type='multipart/form-data')
    assert create_resp.status_code == 201

    item_id = create_resp.get_json()['id']
    detail_resp = client.get(f'/api/items/{item_id}')
    assert detail_resp.status_code == 200
    images = detail_resp.get_json()['images']
    assert len(images) == 1
    image_url = images[0]
    assert image_url.startswith('/api/media/')

    img_resp = client.get(image_url)
    assert img_resp.status_code == 200


def test_my_profile_and_update(client, app):
    client.post('/api/auth/register', data={
        'email': 'profileuser@example.com',
        'username': 'profileuser',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'profileuser@example.com',
        'password': 'StrongPass123!',
    })

    me_resp = client.get('/api/me')
    assert me_resp.status_code == 200
    data = me_resp.get_json()
    assert data['username'] == 'profileuser'
    assert data['email'] == 'profileuser@example.com'

    update_resp = client.patch('/api/me/profile', json={
        'display_name': 'My New Name',
        'bio': 'This is my new bio.'
    })
    assert update_resp.status_code == 200
    update_data = update_resp.get_json()
    assert update_data['display_name'] == 'My New Name'
    assert update_data['bio'] == 'This is my new bio.'

    me_resp = client.get('/api/me')
    assert me_resp.get_json()['display_name'] == 'My New Name'
    assert me_resp.get_json()['bio'] == 'This is my new bio.'


def test_password_change_flow(client, app):
    client.post('/api/auth/register', data={
        'email': 'pwuser@example.com',
        'username': 'pwuser',
        'password': 'OldStrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'pwuser@example.com',
        'password': 'OldStrongPass123!',
    })

    # 1. Change password with wrong current password - should fail
    resp = client.patch('/api/me/password', json={
        'current_password': 'WrongPass123!',
        'new_password': 'NewStrongPass123!',
        'new_password_confirm': 'NewStrongPass123!'
    })
    assert resp.status_code == 401

    # 2. Change password with weak password - should fail
    resp = client.patch('/api/me/password', json={
        'current_password': 'OldStrongPass123!',
        'new_password': 'weak',
        'new_password_confirm': 'weak'
    })
    assert resp.status_code == 400

    # 3. Change password with strong password - should succeed
    resp = client.patch('/api/me/password', json={
        'current_password': 'OldStrongPass123!',
        'new_password': 'NewStrongPass123!',
        'new_password_confirm': 'NewStrongPass123!'
    })
    assert resp.status_code == 200

    # 4. Verifying logout - subsequent authenticated route should fail with 401
    me_resp = client.get('/api/me')
    assert me_resp.status_code == 401

    # 5. Verify login with new password succeeds
    login_resp = client.post('/api/auth/login', data={
        'identifier': 'pwuser@example.com',
        'password': 'NewStrongPass123!',
    })
    assert login_resp.status_code == 200


def test_item_update_and_delete(client, app):
    client.post('/api/auth/register', data={
        'email': 'owner@example.com',
        'username': 'owner',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'owner@example.com',
        'password': 'StrongPass123!',
    })

    create_resp = client.post('/api/items', data={
        'title': '자전거',
        'description': '중고 자전거',
        'price': '80000',
    })
    assert create_resp.status_code == 201
    item_id = create_resp.get_json()['id']

    update_resp = client.patch(f'/api/items/{item_id}', json={
        'title': '새 자전거',
        'price': '75000'
    })
    assert update_resp.status_code == 200
    assert update_resp.get_json()['title'] == '새 자전거'
    assert update_resp.get_json()['price'] == 75000.0

    client.post('/api/auth/logout')
    client.post('/api/auth/register', data={
        'email': 'other@example.com',
        'username': 'other',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'other@example.com',
        'password': 'StrongPass123!',
    })

    fail_update = client.patch(f'/api/items/{item_id}', json={'title': '해킹 자전거'})
    assert fail_update.status_code == 403

    fail_delete = client.delete(f'/api/items/{item_id}')
    assert fail_delete.status_code == 403

    client.post('/api/auth/logout')
    client.post('/api/auth/login', data={
        'identifier': 'owner@example.com',
        'password': 'StrongPass123!',
    })

    delete_resp = client.delete(f'/api/items/{item_id}')
    assert delete_resp.status_code == 200

    client.post('/api/auth/logout')
    get_resp = client.get(f'/api/items/{item_id}')
    assert get_resp.status_code == 404


def test_global_chat(client, app):
    client.post('/api/auth/register', data={
        'email': 'chatuser@example.com',
        'username': 'chatuser',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'chatuser@example.com',
        'password': 'StrongPass123!',
    })

    post_resp = client.post('/api/chat/global/messages', json={
        'content': '안녕하세요! 전체 채팅 테스트입니다.'
    })
    assert post_resp.status_code == 201

    get_resp = client.get('/api/chat/global/messages')
    assert get_resp.status_code == 200
    msgs = get_resp.get_json()['messages']
    assert len(msgs) >= 1
    assert msgs[-1]['content'] == '안녕하세요! 전체 채팅 테스트입니다.'
    assert msgs[-1]['username'] == 'chatuser'


def test_report_auto_blocking(client, app):
    client.post('/api/auth/register', data={
        'email': 'victim@example.com',
        'username': 'victim',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'victim@example.com',
        'password': 'StrongPass123!',
    })
    create_resp = client.post('/api/items', data={
        'title': '위험 상품',
        'description': '사기 의심 상품',
        'price': '999999',
    })
    item_id = create_resp.get_json()['id']
    client.post('/api/auth/logout')

    for i in range(5):
        email = f'reporter{i}@example.com'
        uname = f'reporter{i}'
        client.post('/api/auth/register', data={
            'email': email,
            'username': uname,
            'password': 'StrongPass123!',
            'agree_terms': 'on',
        })
        client.post('/api/auth/login', data={
            'identifier': email,
            'password': 'StrongPass123!',
        })
        
        rep_resp = client.post('/api/reports', json={
            'target_type': 'item',
            'target_id': item_id,
            'reason': 'fraud',
            'details': f'fraud report {i}'
        })
        assert rep_resp.status_code == 201
        
        if i == 4:
            assert rep_resp.get_json()['target_status'] == 'blocked'
            
        client.post('/api/auth/logout')

    get_resp = client.get(f'/api/items/{item_id}')
    assert get_resp.status_code == 404


def test_admin_status_overrides(client, app):
    client.post('/api/auth/register', data={
        'email': 'admin2@example.com',
        'username': 'admin2',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    with app.app_context():
        from app.models import User
        from app import db
        user = User.query.filter_by(username='admin2').first()
        user.role = 'admin'
        db.session.commit()

    client.post('/api/auth/login', data={
        'identifier': 'admin2@example.com',
        'password': 'StrongPass123!',
    })

    client.post('/api/auth/register', data={
        'email': 'targetuser@example.com',
        'username': 'targetuser',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    
    with app.app_context():
        target = User.query.filter_by(username='targetuser').first()
        target_id = target.id

    status_resp = client.patch(f'/api/admin/users/{target_id}/status', json={'is_active': False})
    assert status_resp.status_code == 200
    assert status_resp.get_json()['is_active'] is False





