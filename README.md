## Healthcare Appointment Booking Voice Agent

Hackathon-quality MVP for an appointment discovery and booking assistant using FastAPI, SQLite, and a template-based conversation engine powered by Qwen3-Embedding.


###Demo Video Link: 
https://drive.google.com/file/d/1W6_tdsUY3_s2o6SVbCRKxov5_oaTHHsE/view?pli=1

### Features

- **Input form UI** (FastAPI + Jinja2 + Tailwind) to start a job with patient/appointment details.
- **Geo module**: address → lat/lng via Google Geocoding API (with mock fallback).
- **Clinic search**: Google Places API or deterministic mock clinics.
- **Call orchestrator**: sequentially "calls" clinics (mock Twilio) and logs transcripts.
- **Conversation engine**: Qwen3-Embedding-based intent classifier with template replies.
- **Transcript processing**: rule-based extraction of insurance acceptance, date, time, provider.
- **Decision engine**: chooses earliest viable appointment; early-stop if date matches `date_from`.
- **Booking module**: simulates final booking and optionally sends WhatsApp confirmation via PyWhatKit.
- **Mock mode**: fully functional end-to-end flow with no external calls.

### Quickstart

1. **Create and activate a virtualenv** (optional but recommended):

```bash
cd /Users/girishms/Documents/Nvidia_Hackathon
python -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:

```bash
pip install -r requirements.txt
```

3. **Create `.env` from example**:

```bash
cp .env.example .env
```

By default `MOCK_CALLS=true` and `SEND_WHATSAPP=false`, so the app runs fully locally without hitting Google Maps, Twilio, or WhatsApp.

4. **Run the FastAPI app**:

```bash
uvicorn main:app --reload
```

5. **Open the UI**:

- Navigate to `http://localhost:8000` in your browser.
- Fill in the form and submit.
- You will be redirected to `/job/{id}` where you can see:
  - patient info
  - clinics discovered (mock)
  - call status and transcripts (mock conversations)
  - appointment options
  - best appointment highlighted
  - booking and WhatsApp status

### Architecture Overview

- **`main.py`**: FastAPI app, routes, and job pipeline orchestration.
- **`app_config.py`**: environment-driven configuration.
- **`db.py`** and **`models.py`**: SQLite database and ORM models (jobs, clinics, calls, appointments).
- **`services/geo.py`**: geocoding via Google Geocoding API (mock if no key).
- **`services/clinics.py`**: Google Places-based clinic search with mock clinics.
- **`services/conversation.py`**: Qwen3-Embedding intent classifier and response templates loader.
- **`services/conversation_templates.json`**: intents, examples, and phone-friendly responses.
- **`services/transcripts.py`**: rule-based extraction utilities from transcripts.
- **`services/decision.py`**: selecting the best appointment.
- **`services/calls.py`**: call simulation / Twilio hook and extraction pipeline.
- **`services/booking.py`**: discovery phase driver and final booking + WhatsApp.
- **`services/whatsapp.py`**: PyWhatKit integration with robust logging.
- **`templates/*.html`**: Jinja2 templates for the home and job detail pages.

The conversation engine is intentionally modular: you can later swap out the template-based replies with a generative model (e.g., Qwen 14B) by changing only `services/conversation.py`.

### Sample cURL Commands

Start a job directly via API:

```bash
curl -X POST http://localhost:8000/jobs/start \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "patient_name=Alice Doe" \
  -d "patient_address=1600 Amphitheatre Parkway, Mountain View, CA" \
  -d "patient_phone=5551234567" \
  -d "doctor_specialization=Cardiologist" \
  -d "insurance_company=Demo Insurance" \
  -d "max_radius_miles=10" \
  -d "date_from=2026-03-20" \
  -d "date_to=2026-03-30" \
  -d "priority=earliest" \
  -d "health_issue_brief=Shortness of breath and chest discomfort"
```

Then open the returned `/job/{id}` URL in your browser.

### Production TODOs

- Plug in real Twilio Voice calls and transcription instead of mock conversations.
- Harden Google Maps error handling, retries, and quota management.
- Add authentication / basic access control for the UI.
- Improve NLP around date/time and insurance extraction.
- Add background job processing (Celery, RQ, or async tasks) for non-blocking calls.

