"""ACA-Py multitenancy client: create tenant, get token, list credentials."""
import httpx
from config import get_settings

_settings = get_settings()


async def create_tenant(label: str, wallet_key: str | None = None) -> dict | None:
    """Create a multitenant subwallet. Returns { wallet_id, token } or None if ACA-Py not configured.
    If wallet_key is provided, the wallet is created with that key (caller must store it)."""
    if not _settings.acapy_admin_url.strip():
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {}
        if _settings.acapy_admin_api_key:
            headers["X-API-Key"] = _settings.acapy_admin_api_key
        body: dict = {"label": label}
        if wallet_key:
            body["wallet_key"] = wallet_key
        try:
            r = await client.post(
                f"{_settings.acapy_admin_url.rstrip('/')}/multitenancy/tenant",
                json=body,
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


async def get_tenant_token(wallet_id: str, wallet_key: str | None = None) -> str | None:
    """Get a new token for an existing tenant. wallet_key required by some multitenant providers."""
    if not _settings.acapy_admin_url.strip():
        return None
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {}
        if _settings.acapy_admin_api_key:
            headers["X-API-Key"] = _settings.acapy_admin_api_key
        body: dict = {}
        if wallet_key:
            body["wallet_key"] = wallet_key
        try:
            r = await client.post(
                f"{_settings.acapy_admin_url.rstrip('/')}/multitenancy/tenant/{wallet_id}/token",
                json=body if body else None,
                headers=headers,
            )
            r.raise_for_status()
            return r.json().get("token")
        except Exception:
            return None


async def list_credentials(tenant_token: str | None) -> list:
    """List W3C credentials in the tenant wallet. POST /credentials/w3c with empty body.
    Returns list of credential records (e.g. with credential_id and credential or raw W3C creds)."""
    if not _settings.acapy_admin_url.strip() or not tenant_token:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.post(
                f"{_settings.acapy_admin_url.rstrip('/')}/credentials/w3c",
                json={},
                headers={"Authorization": f"Bearer {tenant_token}"},
            )
            r.raise_for_status()
            data = r.json()
            # Accept { "results": [...] } or a direct list
            if isinstance(data, list):
                return data
            return data.get("results", [])
        except Exception:
            return []


async def agent_status() -> dict:
    """Return agent (ACA-Py) status for admin: reachable, version if available. No secrets."""
    if not _settings.acapy_admin_url.strip():
        return {"configured": False, "reachable": False, "detail": "ACAPY_ADMIN_URL not set"}
    async with httpx.AsyncClient(timeout=5.0) as client:
        headers = {}
        if _settings.acapy_admin_api_key:
            headers["X-API-Key"] = _settings.acapy_admin_api_key
        try:
            r = await client.get(
                f"{_settings.acapy_admin_url.rstrip('/')}/status",
                headers=headers,
            )
            r.raise_for_status()
            data = r.json() if r.content else {}
            return {
                "configured": True,
                "reachable": True,
                "version": data.get("version"),
                "label": data.get("label"),
            }
        except httpx.ConnectError:
            return {"configured": True, "reachable": False, "detail": "Connection refused or unreachable"}
        except httpx.TimeoutException:
            return {"configured": True, "reachable": False, "detail": "Connection timed out"}
        except httpx.HTTPStatusError as e:
            return {"configured": True, "reachable": True, "detail": f"Agent returned {e.response.status_code}"}
        except Exception as e:
            return {"configured": True, "reachable": False, "detail": str(e)}
