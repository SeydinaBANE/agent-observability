import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.models import Tenant

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(key: str) -> str:
    return pwd_context.hash(key)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    return pwd_context.verify(plain_key, hashed_key)


def create_access_token(tenant_id: str, agent_id: str | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": tenant_id,
        "agent_id": agent_id,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


async def get_tenant_from_api_key(
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    result = await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))
    tenants = result.scalars().all()
    for tenant in tenants:
        if verify_api_key(api_key, tenant.api_key_hash):
            return tenant
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


async def get_tenant_from_bearer(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Tenant | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.jwt_algorithm])
        tenant_id = payload.get("sub")
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        result = await db.execute(select(Tenant).where(Tenant.id == uuid.UUID(tenant_id), Tenant.is_active.is_(True)))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant not found")
        return tenant
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


async def _get_tenant_from_api_key_optional(
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Tenant | None:
    if not api_key:
        return None
    result = await db.execute(select(Tenant).where(Tenant.is_active.is_(True)))
    tenants = result.scalars().all()
    for tenant in tenants:
        if verify_api_key(api_key, tenant.api_key_hash):
            return tenant
    return None


async def get_authenticated_tenant(
    api_key_tenant: Tenant | None = Depends(_get_tenant_from_api_key_optional),
    bearer_tenant: Tenant | None = Depends(get_tenant_from_bearer),
) -> Tenant:
    if api_key_tenant:
        return api_key_tenant
    if bearer_tenant:
        return bearer_tenant
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
