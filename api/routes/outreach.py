"""Outreach endpoints — batch draft generation, queue management, sending."""

import logging
import random
import time
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.schemas import (
    OutreachGenerateRequest, OutreachGenerateResponse,
    OutreachQueueResponse, OutreachMessageOut,
    OutreachApproveRequest, OutreachApproveResponse,
    OutreachEditRequest, OutreachSendResponse, SendStatusResponse,
)
from api.services.outreach_service import generate_batch, create_send_job, get_send_job, SendJob
from api.services.gmail_service import GmailService
from api.deps import get_db, get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/outreach", tags=["outreach"])


@router.post("/generate", response_model=OutreachGenerateResponse)
def batch_generate(body: OutreachGenerateRequest):
    db = get_db()
    settings = get_settings()
    result = generate_batch(db=db, lead_ids=body.lead_ids, template=body.template, dedup_days=settings.outreach_dedup_days)
    return OutreachGenerateResponse(
        generated=result["generated"],
        skipped=result["skipped"],
        messages=[OutreachMessageOut(**m) for m in result["messages"]],
    )


@router.get("/queue", response_model=OutreachQueueResponse)
def get_queue(status: str | None = None, page: int = 1, page_size: int = 50):
    db = get_db()
    messages = db.list_outreach_messages(status=status)
    total = len(messages)
    start = (page - 1) * page_size
    page_items = messages[start : start + page_size]
    return OutreachQueueResponse(
        items=[OutreachMessageOut(**m) for m in page_items],
        total=total,
    )


@router.patch("/queue/{msg_id}", response_model=OutreachMessageOut)
def edit_message(msg_id: int, body: OutreachEditRequest):
    db = get_db()
    msg = db.get_outreach_message(msg_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    if body.subject is not None or body.body is not None:
        db.update_outreach_content(msg_id, subject=body.subject, body=body.body)
    if body.status is not None:
        db.update_outreach_status(msg_id, body.status)
    return OutreachMessageOut(**db.get_outreach_message(msg_id))


@router.post("/approve", response_model=OutreachApproveResponse)
def approve_messages(body: OutreachApproveRequest):
    db = get_db()
    count = 0
    for msg_id in body.ids:
        msg = db.get_outreach_message(msg_id)
        if msg and msg["status"] == "draft":
            db.update_outreach_status(msg_id, "approved")
            count += 1
    return OutreachApproveResponse(approved=count)


@router.post("/send", response_model=OutreachSendResponse)
def send_approved(background_tasks: BackgroundTasks):
    db = get_db()
    settings = get_settings()
    creds = db.get_gmail_credentials()
    if not creds:
        raise HTTPException(status_code=400, detail="Gmail not connected")
    approved = db.list_outreach_messages(status="approved")
    if not approved:
        raise HTTPException(status_code=400, detail="No approved messages to send")
    if len(approved) > 20:
        approved = approved[:20]
    job = create_send_job(total=len(approved))
    background_tasks.add_task(_send_batch, job, approved, settings, db)
    return OutreachSendResponse(job_id=job.job_id, total=job.total)


def _send_batch(job: SendJob, messages: list[dict], settings, db):
    """Background task: send emails sequentially with delays."""
    gmail = GmailService(
        encryption_key=settings.encryption_key,
        client_id=settings.gmail_client_id,
        client_secret=settings.gmail_client_secret,
        redirect_uri=settings.gmail_redirect_uri,
    )
    creds = db.get_gmail_credentials()
    if not creds:
        job.complete()
        return

    try:
        token_data = gmail.refresh_access_token(creds["encrypted_refresh_token"])
        access_token = token_data["access_token"]
        db.store_gmail_credentials(
            email_address=creds["email_address"],
            encrypted_refresh_token=creds["encrypted_refresh_token"],
            encrypted_access_token=gmail.encrypt(access_token),
            token_expiry=datetime.now().isoformat(),
        )
    except Exception as e:
        log.error(f"Failed to refresh Gmail token: {e}")
        for msg in messages:
            db.update_outreach_status(msg["id"], "failed", gmail_message_id=str(e))
            job.record_failure(msg["id"], str(e))
        job.complete()
        return

    from_email = creds["email_address"]
    for i, msg in enumerate(messages):
        db.update_outreach_status(msg["id"], "sending")
        try:
            gmail_msg_id = gmail.send_email(
                access_token=access_token, from_email=from_email,
                to_email=msg["to_email"], subject=msg["subject"], body=msg["body"],
            )
            db.update_outreach_status(msg["id"], "sent", gmail_message_id=gmail_msg_id)
            job.record_sent()
            log.info(f"Sent email {i+1}/{len(messages)} to {msg['to_email']}")
        except Exception as e:
            log.error(f"Failed to send to {msg['to_email']}: {e}")
            db.update_outreach_status(msg["id"], "failed", gmail_message_id=str(e))
            job.record_failure(msg["id"], str(e))
        if i < len(messages) - 1:
            delay = random.randint(settings.outreach_send_delay_min, settings.outreach_send_delay_max)
            time.sleep(delay)
    job.complete()


@router.get("/send-status/{job_id}", response_model=SendStatusResponse)
def send_status(job_id: str):
    job = get_send_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return SendStatusResponse(**job.to_dict())


@router.get("/history/{lead_id}")
def lead_history(lead_id: int):
    db = get_db()
    history = db.get_outreach_history(lead_id)
    return [OutreachMessageOut(**m) for m in history]
