/**
 * TinyMarket Global JavaScript Module
 */

async function initGlobalHeader() {
  const headerContainer = document.getElementById('global-header') || document.querySelector('nav');
  if (!headerContainer) return null;

  let auth = { authenticated: false };
  try {
    const res = await fetch('/api/auth/status', { credentials: 'same-origin' });
    auth = await res.json();
  } catch (e) {
    console.error('Failed to fetch auth status', e);
  }

  const currentPath = window.location.pathname;

  let navHtml = `
    <div class="nav-brand">
      <a href="/" class="brand-logo">✨ TinyMarket</a>
    </div>
    <div class="nav-links">
      <a href="/" class="nav-item ${currentPath === '/' ? 'active' : ''}">홈</a>
      <a href="/items" class="nav-item ${currentPath.startsWith('/items') ? 'active' : ''}">상품 목록</a>
    </div>
    <div class="nav-user">
  `;

  if (auth.authenticated && auth.user) {
    const isAdmin = auth.user.role === 'admin';
    navHtml += `
      <span class="user-chip">👋 <strong>${auth.user.username}</strong>님</span>
      ${isAdmin ? `<a href="/admin" class="btn-nav-outline ${currentPath === '/admin' ? 'active' : ''}" style="border-color: var(--accent-purple); color: #a78bfa;">🛡️ 관리자</a>` : ''}
      <a href="/dashboard" class="btn-nav ${currentPath === '/dashboard' ? 'active' : ''}">대시보드</a>
      <button id="global-logout-btn" class="btn-logout" type="button">로그아웃</button>
    `;
  } else {
    navHtml += `
      <a href="/login" class="btn-nav-outline">로그인</a>
      <a href="/register" class="btn-nav-primary">회원가입</a>
    `;
  }

  navHtml += `</div>`;

  headerContainer.className = 'global-navbar';
  headerContainer.innerHTML = navHtml;

  const logoutBtn = document.getElementById('global-logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      const csrfRes = await fetch('/api/auth/csrf-token');
      const csrfData = await csrfRes.json().catch(() => ({}));
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfData.csrf_token || '' }
      });
      window.location.href = '/';
    });
  }

  return auth;
}

async function getCsrfToken() {
  try {
    const res = await fetch('/api/auth/csrf-token');
    const data = await res.json();
    return data.csrf_token || '';
  } catch (e) {
    return '';
  }
}

function formatPrice(amount) {
  return Number(amount || 0).toLocaleString() + '원';
}

function getStatusBadge(status) {
  switch (status) {
    case 'available':
      return '<span class="status-badge available">판매중</span>';
    case 'reserved':
      return '<span class="status-badge reserved">예약중</span>';
    case 'sold':
      return '<span class="status-badge sold">판매완료</span>';
    default:
      return `<span class="status-badge">${status || '상태없음'}</span>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initGlobalHeader();
});
