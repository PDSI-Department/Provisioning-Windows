"""
Webhook sender with retry queue.

Sends provisioning results to a webhook URL. If sending fails,
the payload is queued in SQLite for background retry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import httpx

from app.db.repository import Repository
from app.models.app_config import WebhookSection

logger = logging.getLogger(__name__)


class WebhookSender:
    """Sends JSON payloads to a webhook endpoint with retry support."""

    def __init__(self, config: WebhookSection, repo: Repository):
        self.config = config
        self.repo = repo

    def send(self, run_id: str, payload: dict) -> bool:
        """
        Attempt to send payload to webhook URL.
        If it fails, queue for retry.

        Returns True if sent successfully, False if queued.
        """
        if not self.config.enabled or not self.config.url:
            logger.info("Webhook disabled or no URL configured, skipping")
            return False

        success = self._post(payload)

        if success:
            self.repo.audit("INFO", "webhook", f"Webhook sent for run {run_id}")
            return True

        # Queue for retry
        logger.warning("Webhook send failed, queuing for retry")
        self.repo.enqueue_webhook(
            run_id=run_id,
            payload=payload,
            max_retries=self.config.max_retries,
        )
        self.repo.audit("WARN", "webhook", f"Webhook queued for retry: run {run_id}")
        return False

    def process_retry_queue(self) -> int:
        """
        Process all pending items in the webhook retry queue.
        Returns number of successfully sent items.
        """
        pending = self.repo.get_pending_webhooks()
        if not pending:
            return 0

        sent_count = 0
        now = datetime.now(timezone.utc).isoformat()

        for item in pending:
            try:
                payload = json.loads(item["payload_json"])
            except json.JSONDecodeError:
                self.repo.update_webhook(item["id"], {
                    "status": "failed",
                    "last_error": "Invalid payload JSON",
                    "last_attempt_at": now,
                })
                continue

            success = self._post(payload)

            if success:
                self.repo.update_webhook(item["id"], {
                    "status": "sent",
                    "sent_at": now,
                    "last_attempt_at": now,
                })
                sent_count += 1
                logger.info("Retry webhook sent: queue id %d", item["id"])
            else:
                new_count = item["retry_count"] + 1
                new_status = "failed" if new_count >= item["max_retries"] else "pending"
                self.repo.update_webhook(item["id"], {
                    "retry_count": new_count,
                    "status": new_status,
                    "last_attempt_at": now,
                    "last_error": f"Attempt {new_count} failed",
                })

        return sent_count

    def _post(self, payload: dict) -> bool:
        """POST JSON payload to webhook URL. Returns True on 2xx."""
        try:
            headers = {"Content-Type": "application/json", **self.config.headers}
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(self.config.url, json=payload, headers=headers)

            if 200 <= resp.status_code < 300:
                logger.debug("Webhook POST success: %d", resp.status_code)
                return True

            logger.warning("Webhook POST failed: HTTP %d", resp.status_code)
            return False

        except httpx.TimeoutException:
            logger.warning("Webhook POST timed out")
            return False
        except httpx.RequestError as exc:
            logger.warning("Webhook POST error: %s", exc)
            return False

    def test_send(self, payload: dict | None = None) -> tuple[bool, str]:
        """
        Send a test payload without queue side effects.
        Returns (success, message).
        """
        if not self.config.url:
            return False, "Webhook URL kosong"

        data = payload or {
            "event": "winprov_webhook_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "winprov-ui",
        }
        headers = {"Content-Type": "application/json", **self.config.headers}

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                resp = client.post(self.config.url, json=data, headers=headers)
            if 200 <= resp.status_code < 300:
                return True, f"Success (HTTP {resp.status_code})"
            return False, f"Failed (HTTP {resp.status_code})"
        except httpx.TimeoutException:
            return False, "Timed out"
        except httpx.RequestError as exc:
            return False, f"Request error: {exc}"
