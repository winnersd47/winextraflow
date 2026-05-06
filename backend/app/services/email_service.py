"""Email service — send transactional emails (SMTP or console fallback).

Supports: email verification, password reset, welcome emails.
Uses SMTP when configured, otherwise logs to console (dev mode).
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    def _send(self, to: str, subject: str, html: str):
        """Send email via SMTP or log to console."""
        if not settings.smtp_host or not settings.smtp_user:
            logger.info(f"[EMAIL DEMO] To: {to} | Subject: {subject}")
            logger.info(f"[EMAIL DEMO] Body: {html[:200]}...")
            return

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.smtp_from or settings.smtp_user
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_port == 587:
                    server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent to {to}: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")

    def send_verification(self, to: str, username: str, token: str):
        url = f"{settings.frontend_url}/verify-email?token={token}"
        self._send(to, "WinExtraFlow — Verify your email", f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px">
            <h2 style="color:#22c55e">WinExtraFlow</h2>
            <p>Hi {username},</p>
            <p>Please verify your email address:</p>
            <a href="{url}" style="display:inline-block;background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold">
                Verify Email
            </a>
            <p style="color:#888;font-size:12px;margin-top:20px">Or copy this link: {url}</p>
        </div>
        """)

    def send_password_reset(self, to: str, username: str, token: str):
        url = f"{settings.frontend_url}/reset-password?token={token}"
        self._send(to, "WinExtraFlow — Reset your password", f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px">
            <h2 style="color:#22c55e">WinExtraFlow</h2>
            <p>Hi {username},</p>
            <p>You requested a password reset. Click below:</p>
            <a href="{url}" style="display:inline-block;background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold">
                Reset Password
            </a>
            <p style="color:#888;font-size:12px;margin-top:20px">Link expires in 1 hour. If you didn't request this, ignore this email.</p>
        </div>
        """)

    def send_welcome(self, to: str, username: str):
        self._send(to, "Welcome to WinExtraFlow!", f"""
        <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:20px">
            <h2 style="color:#22c55e">Welcome, {username}!</h2>
            <p>Your WinExtraFlow account is ready.</p>
            <p>Get started:</p>
            <ul>
                <li>Browse trading signals on your dashboard</li>
                <li>Subscribe to strategies on the Marketplace</li>
                <li>Invite friends and earn Premium days</li>
            </ul>
            <a href="{settings.frontend_url}/dashboard" style="display:inline-block;background:#22c55e;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold">
                Open Dashboard
            </a>
        </div>
        """)


email_service = EmailService()
