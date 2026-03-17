from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship, Mapped

from db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = Column(String, default="pending")  # pending, running, completed, failed

    patient_name: Mapped[str] = Column(String)
    patient_address: Mapped[str] = Column(String)
    patient_phone: Mapped[str] = Column(String)
    doctor_specialization: Mapped[str] = Column(String)
    insurance_company: Mapped[str] = Column(String)
    max_radius_miles: Mapped[float] = Column(Float)
    date_from: Mapped[str] = Column(String)
    date_to: Mapped[str] = Column(String)
    priority: Mapped[str] = Column(String)
    health_issue_brief: Mapped[str] = Column(String)

    best_appointment_option_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("appointment_options.id"), nullable=True)
    booking_status: Mapped[str] = Column(String, default="not_started")  # not_started, booked, failed
    whatsapp_status: Mapped[str] = Column(String, default="not_sent")  # not_sent, sent, failed, skipped

    clinics: Mapped[list["Clinic"]] = relationship("Clinic", back_populates="job", cascade="all, delete-orphan")
    calls: Mapped[list["CallLog"]] = relationship("CallLog", back_populates="job", cascade="all, delete-orphan")
    appointment_options: Mapped[list["AppointmentOption"]] = relationship(
        "AppointmentOption",
        back_populates="job",
        cascade="all, delete-orphan",
        foreign_keys="AppointmentOption.job_id",
    )


class Clinic(Base):
    __tablename__ = "clinics"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = Column(Integer, ForeignKey("jobs.id"))

    name: Mapped[str] = Column(String)
    address: Mapped[str] = Column(String)
    phone: Mapped[str] = Column(String)
    rating: Mapped[Optional[float]] = Column(Float, nullable=True)
    latitude: Mapped[Optional[float]] = Column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = Column(Float, nullable=True)

    state: Mapped[str] = Column(
        String, default="pending"
    )  # pending, calling, collected, unsuitable, booked

    job: Mapped["Job"] = relationship("Job", back_populates="clinics")
    calls: Mapped[list["CallLog"]] = relationship("CallLog", back_populates="clinic", cascade="all, delete-orphan")
    appointment_options: Mapped[list["AppointmentOption"]] = relationship(
        "AppointmentOption", back_populates="clinic", cascade="all, delete-orphan"
    )


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = Column(Integer, ForeignKey("jobs.id"))
    clinic_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("clinics.id"), nullable=True)

    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    direction: Mapped[str] = Column(String, default="outbound")
    status: Mapped[str] = Column(String, default="initiated")  # initiated, completed, failed

    transcript: Mapped[str] = Column(Text, default="")
    twilio_call_sid: Mapped[Optional[str]] = Column(String, nullable=True)
    extracted_insurance_ok: Mapped[Optional[bool]] = Column(Boolean, nullable=True)
    extracted_date: Mapped[Optional[str]] = Column(String, nullable=True)
    extracted_time: Mapped[Optional[str]] = Column(String, nullable=True)
    extracted_provider: Mapped[Optional[str]] = Column(String, nullable=True)

    job: Mapped["Job"] = relationship("Job", back_populates="calls")
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="calls")


class AppointmentOption(Base):
    __tablename__ = "appointment_options"

    id: Mapped[int] = Column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = Column(Integer, ForeignKey("jobs.id"))
    clinic_id: Mapped[int] = Column(Integer, ForeignKey("clinics.id"))

    date: Mapped[str] = Column(String)
    time: Mapped[str] = Column(String)
    provider: Mapped[Optional[str]] = Column(String, nullable=True)
    insurance_accepted: Mapped[Optional[bool]] = Column(Boolean, nullable=True)
    is_selected_best: Mapped[bool] = Column(Boolean, default=False)

    job: Mapped["Job"] = relationship("Job", back_populates="appointment_options", foreign_keys=[job_id])
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="appointment_options")

