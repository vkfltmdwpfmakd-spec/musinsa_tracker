from datetime import datetime, timedelta
from typing import Optional
import os
import secrets
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import logging

load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

# JWT 보안 강화 설정
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    # 프로덕션에서는 반드시 강력한 키 설정 필요
    logger.warning("JWT_SECRET_KEY가 설정되지 않았거나 너무 짧습니다. 임시 키 생성 중...")
    SECRET_KEY = secrets.token_urlsafe(32)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# API 키 설정
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger.warning("API_KEY가 설정되지 않았습니다. 기본 키 사용 중...")
    API_KEY = "musinsa-tracker-api-key-2024"

# 패스워드 해싱
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # 보안 강화를 위해 rounds 증가
)

# HTTP Bearer 토큰 인증
security = HTTPBearer(auto_error=False)  # 더 나은 에러 핸들링을 위해


class SecurityConfig:
    """보안 설정 클래스"""
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION = timedelta(minutes=15)
    TOKEN_BLACKLIST = set()  # 실제로는 Redis 등 외부 저장소 사용 권장

    @classmethod
    def is_token_blacklisted(cls, token: str) -> bool:
        """토큰이 블랙리스트에 있는지 확인"""
        return token in cls.TOKEN_BLACKLIST

    @classmethod
    def blacklist_token(cls, token: str):
        """토큰을 블랙리스트에 추가"""
        cls.TOKEN_BLACKLIST.add(token)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"비밀번호 검증 중 오류: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    """비밀번호 해싱"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT 토큰 생성"""
    to_encode = data.copy()

    # 토큰 만료 시간 설정
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # 추가 클레임으로 보안 강화
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),  # 발급 시간
        "jti": secrets.token_urlsafe(16),  # JWT ID (토큰 추적용)
        "type": "access_token"
    })

    try:
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"JWT 토큰 생성 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail="토큰 생성에 실패했습니다")


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """JWT 토큰 검증 """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="인증 토큰이 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 블랙리스트 확인
    if SecurityConfig.is_token_blacklisted(token):
        raise HTTPException(
            status_code=401,
            detail="무효한 토큰입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        # 토큰 디코딩 및 검증
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # 필수 클레임 확인
        username: str = payload.get("sub")
        token_type: str = payload.get("type")

        if username is None or token_type != "access_token":
            raise HTTPException(
                status_code=401,
                detail="토큰이 유효하지 않습니다",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 토큰 만료 시간 추가 확인
        exp = payload.get("exp")
        if exp and datetime.utcnow().timestamp() > exp:
            raise HTTPException(
                status_code=401,
                detail="토큰이 만료되었습니다",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return username

    except JWTError as e:
        logger.warning(f"JWT 토큰 검증 실패: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="토큰이 유효하지 않습니다",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"토큰 검증 중 예상치 못한 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="토큰 검증에 실패했습니다"
        )


def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)) -> bool:
    """API 키 검증"""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API 키가 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_key = credentials.credentials

    # 타이밍 공격 방지를 위한 상수 시간 비교
    if not secrets.compare_digest(provided_key, API_KEY):
        logger.warning(f"잘못된 API 키 사용 시도")
        raise HTTPException(
            status_code=401,
            detail="유효하지 않은 API 키입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return True


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """현재 사용자 정보 반환 (JWT 또는 API 키 둘 다 지원)"""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="인증이 필요합니다",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT 토큰 우선 시도
    try:
        return verify_token(credentials)
    except HTTPException as jwt_error:
        # JWT 실패 시 API 키로 시도
        try:
            verify_api_key(credentials)
            return "api_user"
        except HTTPException:
            # 둘 다 실패하면 JWT 오류 반환 (더 구체적)
            raise jwt_error


def logout_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """토큰 로그아웃 (블랙리스트 추가)"""
    if credentials:
        token = credentials.credentials
        SecurityConfig.blacklist_token(token)
        logger.info("토큰이 로그아웃되었습니다")

    return {"message": "성공적으로 로그아웃되었습니다"}


# 환경변수 검증 함수
def validate_security_config():
    """보안 설정 검증"""
    issues = []

    if not SECRET_KEY or len(SECRET_KEY) < 32:
        issues.append("JWT_SECRET_KEY가 32자 미만이거나 설정되지 않음")

    if API_KEY == "musinsa-tracker-api-key-2024":
        issues.append("기본 API_KEY 사용 중 - 프로덕션에서 변경 필요")

    if issues:
        logger.warning("보안 설정 문제: " + ", ".join(issues))

    return len(issues) == 0