from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session
from twilio.rest import Client

from app_config import settings
from models import AppointmentOption, CallLog, Clinic, Job
from services.conversation import get_conversation_engine
from services.transcripts import extract_datetime, extract_insurance_ok, extract_provider


def _mock_conversation(job: Job, clinic: Clinic) -> str:
    """
    Simulate a full call transcript for demo / tests.
    """
    lines: List[str] = []
    engine = get_conversation_engine()
    ctx = {
        "insurance_company": job.insurance_company,
        "specialization": job.doctor_specialization,
        "health_issue_brief": job.health_issue_brief,
        "summary": "",
    }

    # Greeting
    intent, _ = engine.classify_intent("hello")
    lines.append(f"Agent: {engine.generate_reply(intent, ctx)}")
    lines.append("Clinic: Hello, how can I help you?")

    # Ask insurance
    intent, _ = engine.classify_intent("insurance")
    lines.append(f"Agent: {engine.generate_reply('ask_insurance', ctx)}")
    lines.append("Clinic: Yes, we accept that insurance.")

    # Ask availability
    intent, _ = engine.classify_intent("earliest appointment")
    lines.append(f"Agent: {engine.generate_reply('ask_availability', ctx)}")
    # simple deterministic date: job.date_from at 10:00
    lines.append(f"Clinic: Our next available is {job.date_from} at 10:00 AM with Dr. Smith.")

    # Optionally mention issue if asked
    lines.append("Clinic: What is the patient's main issue?")
    lines.append(f"Agent: {engine.generate_reply('provide_issue', ctx)}")

    return "\n".join(lines)


def perform_call_and_extract(db: Session, job: Job, clinic: Clinic) -> Tuple[CallLog, Optional[AppointmentOption]]:
    """
    Core call orchestration. In MOCK_CALLS mode we simulate; otherwise this is where
    Twilio integration would live.
    """
    call = CallLog(job=job, clinic=clinic, status="initiated", direction="outbound")
    db.add(call)
    db.flush()

    appointment: Optional[AppointmentOption] = None

    if settings.mock_calls:
        # Fully simulated call and extraction.
        transcript = _mock_conversation(job, clinic)
        call.transcript = transcript
        call.status = "completed"

        ins_ok = extract_insurance_ok(transcript)
        date, time = extract_datetime(transcript)
        provider = extract_provider(transcript)

        call.extracted_insurance_ok = ins_ok
        call.extracted_date = date
        call.extracted_time = time
        call.extracted_provider = provider

        if date and time:
            appointment = AppointmentOption(
                job=job,
                clinic=clinic,
                date=date,
                time=time,
                provider=provider,
                insurance_accepted=ins_ok,
            )
            db.add(appointment)
    else:
        # Real Twilio outbound call; we do NOT fabricate appointment data.
        # The dashboard will show that a call was placed (with the Twilio SID)
        # but no appointment option will be auto-created until a real
        # transcription / parsing pipeline is added.
        transcript_header = ""
        try:
            if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number:
                client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
                twilio_call = client.calls.create(
                    to=clinic.phone,
                    from_=settings.twilio_phone_number,
                    url=f"{settings.base_url}/twilio/voice?job_id={job.id}&clinic_id={clinic.id}",
                )
                call.twilio_call_sid = twilio_call.sid
                transcript_header = f"[Real Twilio call placed. Call SID: {twilio_call.sid}]\n"
            else:
                transcript_header = "[Twilio not fully configured; no real call placed.]\n"
        except Exception as exc:  # noqa: BLE001
            transcript_header = f"[Twilio call failed: {exc}]\n"

        call.transcript = transcript_header + "No automatic transcription yet. Please check the Twilio console for call details."
        call.status = "completed"

    return call, appointment

