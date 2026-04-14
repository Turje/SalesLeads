"""Gmail OAuth2 authentication endpoints."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from api.schemas import GmailStatusResponse
from api.services.gmail_service import GmailService
from api.deps import get_db, get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_gmail_service() -> GmailService:
    settings = get_settings()
    return GmailService(
        encryption_key=settings.encryption_key,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        redirect_uri=settings.gmail_redirect_uri,
    )


@router.get("/gmail")
def gmail_auth():
    svc = _get_gmail_service()
    if not svc.client_id:
        raise HTTPException(status_code=500, detail="Gmail client ID not configured")
    return {"auth_url": svc.get_auth_url()}


@router.get("/gmail/callback", response_class=HTMLResponse)
def gmail_callback(code: str):
    svc = _get_gmail_service()
    db = get_db()
    try:
        token_data = svc.exchange_code(code)
    except Exception as e:
        return HTMLResponse(f"<html><body><h2>Authentication failed</h2><p>{e}</p></body></html>", status_code=400)

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    try:
        email = svc.get_user_email(access_token)
    except Exception:
        email = "unknown"

    db.store_gmail_credentials(
        email_address=email,
        encrypted_refresh_token=svc.encrypt(refresh_token),
        encrypted_access_token=svc.encrypt(access_token),
        token_expiry=token_data.get("expires_in", ""),
    )

    return HTMLResponse("""
    <html><body>
    <h2>Gmail connected successfully!</h2>
    <p>You can close this window.</p>
    <script>
        if (window.opener) {
            window.opener.postMessage({ gmail: "connected" }, "*");
        }
        setTimeout(() => window.close(), 1500);
    </script>
    </body></html>
    """)


@router.get("/gmail/status", response_model=GmailStatusResponse)
def gmail_status():
    db = get_db()
    creds = db.get_gmail_credentials()
    if not creds:
        return GmailStatusResponse(connected=False)
    return GmailStatusResponse(connected=True, email=creds["email_address"])


@router.delete("/gmail")
def gmail_disconnect():
    db = get_db()
    db.delete_gmail_credentials()
    return {"disconnected": True}
