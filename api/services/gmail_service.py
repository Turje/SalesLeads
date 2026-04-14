"""Gmail API integration — OAuth2 authentication and email sending."""

import base64
import logging
from email.mime.text import MIMEText
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet

log = logging.getLogger(__name__)

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.send", "openid", "email"]


class GmailService:
    """Handles Gmail OAuth2 and email sending."""

    def __init__(self, encryption_key: str, client_id: str = "", client_secret: str = "", redirect_uri: str = ""):
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def get_auth_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GMAIL_AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        resp = requests.post(GMAIL_TOKEN_URL, data={
            "code": code, "client_id": self.client_id,
            "client_secret": self.client_secret, "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        })
        resp.raise_for_status()
        return resp.json()

    def refresh_access_token(self, encrypted_refresh_token: str) -> dict:
        refresh_token = self.decrypt(encrypted_refresh_token)
        resp = requests.post(GMAIL_TOKEN_URL, data={
            "refresh_token": refresh_token, "client_id": self.client_id,
            "client_secret": self.client_secret, "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        return resp.json()

    def get_user_email(self, access_token: str) -> str:
        resp = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json().get("email", "")

    def build_mime_message(self, from_email: str, to_email: str, subject: str, body: str) -> str:
        msg = MIMEText(body)
        msg["to"] = to_email
        msg["from"] = from_email
        msg["subject"] = subject
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()

    def send_email(self, access_token: str, from_email: str, to_email: str, subject: str, body: str) -> str:
        raw = self.build_mime_message(from_email, to_email, subject, body)
        resp = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"raw": raw},
        )
        resp.raise_for_status()
        return resp.json().get("id", "")
