"""ACA-Py multitenancy client: create tenant, get token, list credentials."""
import httpx
from config import get_settings

_settings = get_settings()


async def create_tenant(label: str) -> dict | None:
    """Create a multitenant wallet. Returns { wallet_id, token } or None if ACA-Py not configured."""
    if not _settings.acapy_admin_url.strip():
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {}
        if _settings.acapy_admin_api_key:
            headers["X-API-Key"] = _settings.acapy_admin_api_key
        try:
            r = await client.post(
                f"{_settings.acapy_admin_url.rstrip('/')}/multitenancy/tenant",
                json={"label": label},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "wallet_id": data.get("wallet_id"),
                "token": data.get("token"),
            }
        except Exception:
            return None


async def get_tenant_token(wallet_id: str) -> str | None:
    """Get a new token for an existing tenant."""
    if not _settings.acapy_admin_url.strip():
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {}
        if _settings.acapy_admin_api_key:
            headers["X-API-Key"] = _settings.acapy_admin_api_key
        try:
            r = await client.post(
                f"{_settings.acapy_admin_url.rstrip('/')}/multitenancy/tenant/{wallet_id}/token",
                headers=headers,
            )
            r.raise_for_status()
            return r.json().get("token")
        except Exception:
            return None


async def list_credentials(tenant_token: str | None) -> list:
    """List credentials in the tenant wallet. Returns list of credential records."""
    if not _settings.acapy_admin_url.strip() or not tenant_token:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(
                f"{_settings.acapy_admin_url.rstrip('/')}/credentials",
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception:
            return []
