def test_authenticated_home_page_shows_current_personalized_ui(client):
    client.post('/api/auth/register', data={
        'email': 'currenthome@example.com',
        'username': 'currenthome',
        'password': 'StrongPass123!',
        'agree_terms': 'on',
    })
    client.post('/api/auth/login', data={
        'identifier': 'currenthome@example.com',
        'password': 'StrongPass123!',
    })

    response = client.get('/')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'currenthome' in body
    assert '로그인됨:' in body
    assert 'hero-section' in body
