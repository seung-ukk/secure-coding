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
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest pytest-flask
```

## 3. 환경 변수 설정
프로젝트 루트의 `backend/.env.example` 파일을 참고하여 환경 변수를 설정합니다.
```bash
cp backend/.env.example backend/.env
```
필요 시 `backend/.env` 파일을 열어 다음 값을 확인합니다.
```env
SECRET_KEY=demo-secret-key-change-me
DATABASE_URL=sqlite:///app.db
UPLOAD_FOLDER=/tmp/secure_media
```

## 4. 데이터베이스 초기화
```bash
cd backend
export SECRET_KEY='demo-secret-key-change-me'
export DATABASE_URL='sqlite:///app.db'
export UPLOAD_FOLDER='/tmp/secure_media'
python -m flask --app run db init
python -m flask --app run db migrate -m "initial migration"
python -m flask --app run db upgrade
```

## 5. 애플리케이션 실행
```bash
cd backend
export SECRET_KEY='demo-secret-key-change-me'
export DATABASE_URL='sqlite:///app.db'
export UPLOAD_FOLDER='/tmp/secure_media'
python run.py
```
실행 후 브라우저에서 아래 주소로 접속합니다.
- http://127.0.0.1:5000/health

## 6. 테스트 실행
```bash
cd backend
export SECRET_KEY='demo-secret-key-change-me'
export DATABASE_URL='sqlite:///app.db'
export UPLOAD_FOLDER='/tmp/secure_media'
pytest -q
```

## 참고 사항
- 현재 구현은 학습/시연용 스켈레톤이며, 실제 운영 환경에서는 HTTPS, 강한 비밀키, DB 보안, 파일 업로드 검증, CSRF/세션 보안 강화가 필요합니다.
- 백엔드 앱은 Flask 기반이며, 프론트엔드는 기본 템플릿으로 구성되어 있습니다.
