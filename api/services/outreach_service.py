"""Outreach batch generation and send orchestration."""

import logging
import uuid
from dataclasses import dataclass, field

from core.database import Database
from core.llm_client import LLMClient, LLMError
from api.services.email_service import draft_email
from api.deps import get_settings

log = logging.getLogger(__name__)


def generate_batch(db: Database, lead_ids: list[int], template: str, dedup_days: int = 30) -> dict:
    settings = get_settings()
    llm = LLMClient(base_url=settings.ollama_base_url, model=settings.ollama_model)

    generated = 0
    skipped = []
    messages = []

    for lead_id in lead_ids:
        lead = db.get_lead(lead_id)
        if lead is None:
            skipped.append({"lead_id": lead_id, "reason": "lead not found"})
            continue
        if not lead.email:
            skipped.append({"lead_id": lead_id, "reason": "no email address"})
            continue
        if db.has_recent_outreach(lead_id, template, days=dedup_days):
            skipped.append({"lead_id": lead_id, "reason": f"contacted within last {dedup_days} days"})
            continue

        try:
            result = draft_email(lead=lead, template=template, llm=llm)
        except (LLMError, Exception):
            result = _simple_fallback(lead, template)

        msg_id = db.insert_outreach_message(
            lead_id=lead_id, template=template,
            subject=result["subject"], body=result["body"],
            to_email=lead.email, to_name=lead.contact_name or "",
            model=result.get("model", "template"),
            duration_ms=int(result.get("duration_ms", 0)),
        )
        msg = db.get_outreach_message(msg_id)
        messages.append(msg)
        generated += 1

    return {"generated": generated, "skipped": skipped, "messages": messages}


def _simple_fallback(lead, template: str) -> dict:
    name = (lead.contact_name or "").split()[0] if lead.contact_name else "there"
    company = lead.company_name or "your company"
    if template == "follow_up":
        subject = f"Following up — IT services for {company}"
        body = f"Hi {name},\n\nI wanted to follow up on my previous message about managed IT services for {company}.\n\nWould you be open to a brief call this week?\n\nBest regards"
    elif template == "meeting_request":
        subject = f"Meeting request — {company} IT infrastructure"
        body = f"Hi {name},\n\nI'd love to schedule a 15-minute call to discuss how we can help {company} with IT infrastructure management.\n\nAre you available this week?\n\nBest regards"
    else:
        subject = f"Introduction — Managed IT for {company}"
        body = f"Hi {name},\n\nI'm reaching out because we specialize in managed IT services for commercial real estate properties like {company}.\n\nWould you be open to a brief conversation about your IT needs?\n\nBest regards"
    return {"subject": subject, "body": body, "model": "template", "duration_ms": 0}


@dataclass
class SendJob:
    job_id: str
    total: int
    status: str = "running"
    sent: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)

    def record_sent(self):
        self.sent += 1

    def record_failure(self, msg_id: int, error: str):
        self.failed += 1
        self.errors.append({"message_id": msg_id, "error": error})

    def complete(self):
        self.status = "done"

    def to_dict(self) -> dict:
        return {"job_id": self.job_id, "status": self.status, "sent": self.sent,
                "failed": self.failed, "total": self.total, "errors": self.errors}


_jobs: dict[str, SendJob] = {}


def create_send_job(total: int) -> SendJob:
    job_id = str(uuid.uuid4())[:8]
    job = SendJob(job_id=job_id, total=total)
    _jobs[job_id] = job
    return job


def get_send_job(job_id: str) -> SendJob | None:
    return _jobs.get(job_id)
