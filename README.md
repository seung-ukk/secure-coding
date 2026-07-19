# secure-coding
whs 20260627 시큐어 코딩 수업

## 프로젝트 개요
이 저장소는 Flask 기반의 Tiny Second-hand Shopping Platform 백엔드/프론트엔드 스켈레톤과 핵심 API 엔드포인트를 포함합니다.

## 실행 전 준비사항
다음 도구가 설치되어 있어야 합니다.
- Python 3.10 이상
- Git
- pip

## 1. 저장소 복제
```bash
git clone https://github.com/seung-ukk/secure-coding.git
cd secure-coding
```

## 2. 백엔드 환경 설정
```bash
cd backend
python -m venv .venv

# venv 활성화 (OS에 맞게 선택)
# macOS / Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat

# 의존성 설치
pip install -r requirements.txt
```

## 3. 환경 변수 설정
프로젝트 루트의 `backend/.env.example` 파일을 참고하여 환경 변수를 설정합니다.
```bash
# macOS / Linux:
cp backend/.env.example backend/.env
# Windows (PowerShell):
Copy-Item backend/.env.example backend/.env
```
필요 시 `backend/.env` 파일을 열어 환경 변수를 편집하거나 확인합니다.
* `SECRET_KEY`: 애플리케이션 보안 서명용 키 (운영 환경에서는 반드시 강한 값으로 교체)
* `DATABASE_URL`: 데이터베이스 연결 경로 (기본값: `sqlite:///app.db`)
* `UPLOAD_FOLDER`: 파일 업로드 경로
* `WTF_CSRF_ENABLED`: CSRF 보안 설정 여부 (기본값: `true`)

## 4. 데이터베이스 초기화 및 초기화(Reset) 방법

### 최초 초기화 시:
가상환경이 활성화된 상태에서 아래 명령어를 실행하여 DB 테이블을 생성합니다.
```bash
cd backend
python -m flask --app run db init
python -m flask --app run db migrate -m "initial migration"
python -m flask --app run db upgrade
```

### 테스트 데이터 및 DB 전체 리셋 (초기화) 시:
개발 또는 테스트 중 적재된 임시 데이터(사용자, 상품, 채팅, 신고 기록 등)와 업로드 미디어를 초기화하여 신규 테스트를 진행하고자 할 때 아래 순서대로 수행합니다.

**macOS / Linux:**
```bash
cd backend
# 1. 업로드된 미디어 파일 제거
rm -rf /tmp/secure_media/*

# 2. 기존 SQLite DB 파일 삭제 및 스키마 재구성
rm -f instance/app.db
python -m flask --app run db upgrade
```

**Windows (PowerShell):**
```powershell
cd backend
# 1. 업로드된 미디어 파일 제거
Remove-Item -Path C:/tmp/secure_media/* -Recurse -Force -ErrorAction SilentlyContinue

# 2. 기존 SQLite DB 파일 삭제 및 스키마 재구성
Remove-Item -Path instance/app.db -ErrorAction SilentlyContinue
python -m flask --app run db upgrade
```

## 5. 애플리케이션 실행
가상환경 활성화 상태에서 아래 스크립트를 동작시킵니다.
```bash
cd backend
python run.py
```
실행 후 브라우저에서 아래 주소로 접속합니다.
- http://127.0.0.1:5000/health

## 6. 테스트 실행
작성된 단위/통합 테스트를 가상환경 내에서 수행합니다.
```bash
cd backend
pytest -v
```

## 참고 사항 및 보안 조치 사항 (Security Upgrades)
이 저장소는 시큐어 코딩 실습을 위해 개선 작업이 점진적으로 이루어지고 있습니다. 현재 다음 보안 패치가 적용되었습니다.
- **[SEC-01] 어드민 기능 인가 강화 ([admin/routes.py](file:///c:/Users/yoseb/Desktop/secure-coding/backend/app/admin/routes.py))**:
  - `@admin_required` 데코레이터를 이용해 비인증 사용자 및 일반 사용자의 접근을 차단하고, 실제 신고 데이터 조회 및 감사 로그 생성 기능을 연동했습니다.
- **[SEC-02] CSRF 보안 강화 ([config.py](file:///c:/Users/yoseb/Desktop/secure-coding/backend/app/config.py#L10))**:
  - `WTF_CSRF_ENABLED`가 명시적 변수 제공이 없더라도 기본적으로 활성화(`True`)되도록 보완했습니다. 이에 따라 POST/PUT/PATCH/DELETE 요청 시에는 헤더(`X-CSRFToken`) 등에 토큰을 첨부해야 합니다.
- **향후 개선 대상**:
  - 파일 업로드 시 경로 유출 방지 및 상대적 매핑 경로 반환 로직 도입 예정.
  - 송금 연산(`/api/payments/transfer`)의 무결성 확보를 위한 DB Row Locking 트랜잭션 구현 예정.
