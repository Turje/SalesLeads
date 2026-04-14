"""Tests for GmailService — encryption, MIME building, and OAuth URL generation."""

import base64

import pytest

from api.services.gmail_service import GmailService


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        original = "my_secret_token"
        encrypted = svc.encrypt(original)
        assert encrypted != original
        assert svc.decrypt(encrypted) == original

    def test_generate_key_is_valid(self):
        key = GmailService.generate_key()
        assert isinstance(key, str)
        svc = GmailService(encryption_key=key)
        assert svc.encrypt("test") != "test"


class TestBuildMimeMessage:
    def test_builds_valid_mime(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        raw = svc.build_mime_message(
            from_email="sender@test.com", to_email="recipient@test.com",
            subject="Test Subject", body="Hello, this is a test.",
        )
        assert isinstance(raw, str)
        assert len(raw) > 0

    def test_mime_contains_headers(self):
        svc = GmailService(encryption_key=GmailService.generate_key())
        raw = svc.build_mime_message(
            from_email="sender@test.com", to_email="recipient@test.com",
            subject="Test", body="Body",
        )
        decoded = base64.urlsafe_b64decode(raw + "==").decode("utf-8", errors="replace")
        assert "sender@test.com" in decoded
        assert "recipient@test.com" in decoded


class TestOAuthUrl:
    def test_get_auth_url(self):
        svc = GmailService(
            encryption_key=GmailService.generate_key(),
            client_id="test_client_id", client_secret="test_secret",
            redirect_uri="http://localhost:8000/api/auth/gmail/callback",
        )
        url = svc.get_auth_url()
        assert "accounts.google.com" in url
        assert "test_client_id" in url
