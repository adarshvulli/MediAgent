from __future__ import annotations

from sqlalchemy.orm import Session

from app_config import settings
from models import AppointmentOption, Clinic, Job
from services.calls import perform_call_and_extract
from services.whatsapp import send_whatsapp_confirmation


def run_discovery_phase(db: Session, job: Job) -> None:
    """
    Sequentially call clinics, collect appointment options, and early-stop if
    a clinic offers appointment exactly on job.date_from.
    """
    for clinic in job.clinics:
        clinic.state = "calling"
        call, appt = perform_call_and_extract(db, job, clinic)
        db.flush()

        if not appt:
            clinic.state = "unsuitable"
            continue

        clinic.state = "collected"

        if appt.date == job.date_from:
            # Early stop rule
            break


def perform_final_booking(db: Session, job: Job, best_appt: AppointmentOption) -> None:
    """
    For this MVP, we simulate booking as a simple status update.
    In a real system this would place a second Twilio call or send a fax/portal request.
    """
    clinic: Clinic = best_appt.clinic

    if settings.mock_calls:
        job.booking_status = "booked"
    else:
        # TODO: Implement real booking call here.
        job.booking_status = "booked"

    # WhatsApp notification
    error = send_whatsapp_confirmation(job, best_appt, clinic)
    if error:
        job.whatsapp_status = "failed"
    else:
        job.whatsapp_status = "sent" if settings.send_whatsapp else "skipped"

