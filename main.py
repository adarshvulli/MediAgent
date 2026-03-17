from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app_config import settings
from db import Base, engine, get_db
from models import AppointmentOption, Clinic, Job, CallLog
from services.booking import perform_final_booking, run_discovery_phase
from services.clinics import search_clinics_for_job
from services.decision import pick_best_appointment
from services.geo import geocode_address
from services.transcripts import extract_datetime, extract_insurance_ok, extract_provider

app = FastAPI(title="Healthcare Appointment Booking Voice Agent")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/jobs/start")
async def start_job(
    request: Request,
    patient_name: Annotated[str, Form(...)],
    patient_address: Annotated[str, Form(...)],
    patient_phone: Annotated[str, Form(...)],
    doctor_specialization: Annotated[str, Form(...)],
    insurance_company: Annotated[str, Form(...)],
    max_radius_miles: Annotated[float, Form(...)],
    date_from: Annotated[str, Form(...)],
    date_to: Annotated[str, Form(...)],
    priority: Annotated[str, Form(...)],
    health_issue_brief: Annotated[str, Form(...)],
    db: Session = Depends(get_db),
):
    job = Job(
        patient_name=patient_name.strip(),
        patient_address=patient_address.strip(),
        patient_phone=patient_phone.strip(),
        doctor_specialization=doctor_specialization.strip(),
        insurance_company=insurance_company.strip(),
        max_radius_miles=max_radius_miles,
        date_from=date_from.strip(),
        date_to=date_to.strip(),
        priority=priority.strip(),
        health_issue_brief=health_issue_brief.strip(),
        status="running",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # For MVP we run the whole pipeline synchronously after job creation.
    await _run_pipeline_for_job(job.id, db)

    return RedirectResponse(url=f"/job/{job.id}", status_code=303)


async def _run_pipeline_for_job(job_id: int, db: Session) -> None:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # 1. Geocode
    lat, lng = await geocode_address(job.patient_address)

    # 2. Search clinics
    clinics = await search_clinics_for_job(job, lat, lng)
    for c in clinics:
        db.add(c)
    db.commit()
    db.refresh(job)

    # 3. Discovery calls
    run_discovery_phase(db, job)
    db.commit()
    db.refresh(job)

    # In mock mode, we have local transcripts immediately and can fully
    # complete the workflow synchronously. In real Twilio mode, the
    # transcription will arrive asynchronously via webhook.
    if getattr(settings, "mock_calls", True):
        best = pick_best_appointment(job.appointment_options)
        if best:
            best.is_selected_best = True
            job.best_appointment_option_id = best.id
            perform_final_booking(db, job, best)
            job.status = "completed"
        else:
            job.status = "completed"
        db.commit()


@app.post("/twilio/voice")
async def twilio_voice(
    request: Request,
    job_id: int,
    clinic_id: int,
    db: Session = Depends(get_db),
):
    """
    Twilio webhook to drive the outbound call dialogue.
    For now this is a simple scripted interaction that:
    - Introduces the agent
    - Asks about insurance acceptance
    - Asks for earliest availability
    """
    job = db.get(Job, job_id)
    clinic = db.get(Clinic, clinic_id)
    if not job or not clinic:
        # Minimal TwiML response to avoid Twilio errors.
        twiml = '<?xml version="1.0" encoding="UTF-8"?><Response><Say>Sorry, this call cannot be processed.</Say></Response>'
        return Response(content=twiml, media_type="text/xml")

    # Ask high-level questions, then record the clinic's response and let
    # Twilio generate a transcription which will be sent to our callback.
    callback_url = f"{settings.base_url}/twilio/transcription?job_id={job.id}&clinic_id={clinic.id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">Hello, I'm calling to check appointment availability for a patient.</Say>
  <Pause length="1"/>
  <Say voice="alice">Do you accept {job.insurance_company}?</Say>
  <Pause length="4"/>
  <Say voice="alice">What is your earliest available appointment for a {job.doctor_specialization}?</Say>
  <Pause length="1"/>
  <Say voice="alice">After the tone, please briefly say whether you accept the insurance and the earliest available date and time.</Say>
  <Record transcribe="true" transcribeCallback="{callback_url}" maxLength="60" playBeep="true" />
  <Say voice="alice">Thank you for your time. Goodbye.</Say>
</Response>
"""
    return Response(content=twiml, media_type="text/xml")


@app.post("/twilio/transcription")
async def twilio_transcription(
    request: Request,
    job_id: int,
    clinic_id: int,
    db: Session = Depends(get_db),
):
    """
    Twilio transcription callback. Uses the transcribed text to populate
    the CallLog and create/update an AppointmentOption, then re-runs the
    decision engine and booking logic.
    """
    form = await request.form()
    transcription_text = form.get("TranscriptionText") or ""
    call_sid = form.get("CallSid")

    job = db.get(Job, job_id)
    clinic = db.get(Clinic, clinic_id)
    if not job or not clinic:
        return Response(content="", status_code=204)

    # Find the matching CallLog, preferring the one with this CallSid.
    call: CallLog | None = None
    if call_sid:
        call = (
            db.query(CallLog)
            .filter(
                CallLog.job_id == job.id,
                CallLog.clinic_id == clinic.id,
                CallLog.twilio_call_sid == call_sid,
            )
            .order_by(CallLog.created_at.desc())
            .first()
        )
    if call is None:
        call = (
            db.query(CallLog)
            .filter(
                CallLog.job_id == job.id,
                CallLog.clinic_id == clinic.id,
            )
            .order_by(CallLog.created_at.desc())
            .first()
        )

    if call is None:
        return Response(content="", status_code=204)

    # Append transcription to transcript log.
    call.transcript = (call.transcript or "") + "\n[Twilio transcription]\n" + transcription_text

    ins_ok = extract_insurance_ok(transcription_text)
    date, time = extract_datetime(transcription_text)
    provider = extract_provider(transcription_text)

    call.extracted_insurance_ok = ins_ok
    call.extracted_date = date
    call.extracted_time = time
    call.extracted_provider = provider

    # Create or update an appointment option for this clinic.
    appointment = (
        db.query(AppointmentOption)
        .filter(
            AppointmentOption.job_id == job.id,
            AppointmentOption.clinic_id == clinic.id,
        )
        .order_by(AppointmentOption.id.asc())
        .first()
    )
    if date and time:
        if appointment is None:
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
            appointment.date = date
            appointment.time = time
            appointment.provider = provider
            appointment.insurance_accepted = ins_ok

    # Re-run decision + booking when we have at least one appointment.
    db.flush()
    if job.appointment_options:
        best = pick_best_appointment(job.appointment_options)
        if best:
            for opt in job.appointment_options:
                opt.is_selected_best = opt.id == best.id
            job.best_appointment_option_id = best.id

            # Early-stop rule: if this matches date_from and we haven't booked yet,
            # we can proceed with booking.
            if best.date == job.date_from and job.booking_status == "not_started":
                perform_final_booking(db, job, best)
                job.status = "completed"
            elif job.booking_status == "not_started":
                # If no exact match but we want the earliest overall, book that too.
                perform_final_booking(db, job, best)
                job.status = "completed"

    db.commit()
    return Response(content="", status_code=204)


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Simple eager loading-ish via relationships
    clinics = job.clinics
    calls_by_clinic: dict[int | None, list] = {}
    for call in job.calls:
        calls_by_clinic.setdefault(call.clinic_id, []).append(call)

    best_appt: AppointmentOption | None = None
    if job.best_appointment_option_id:
        best_appt = db.get(AppointmentOption, job.best_appointment_option_id)

    return templates.TemplateResponse(
        "job.html",
        {
            "request": request,
            "job": job,
            "clinics": clinics,
            "calls_by_clinic": calls_by_clinic,
            "appointment_options": job.appointment_options,
            "best_appointment": best_appt,
            "settings": settings,
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

