from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, AliasChoices


DocumentType = Literal["prescription", "bill", "report", "pharmacy_bill", "unknown"]


class DocumentTypeClassification(BaseModel):
    document_type: DocumentType
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    rationale: str | None = None


class BaseExtraction(BaseModel):
    document_type: DocumentType
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    field_confidences: dict[str, float] = Field(default_factory=dict)


class PrescriptionExtraction(BaseExtraction):
    document_type: Literal["prescription"] = "prescription"

    doctor_name: str | None = None
    doctor_reg: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "doctor_reg",
            "doctor_registration_number",
            "doctor_registration_no",
            "doctor_reg_no",
        ),
    )
    patient_name: str | None = Field(default=None, validation_alias=AliasChoices("patient_name", "patient", "name"))
    date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("date", "visit_date", "treatment_date", "prescription_date"),
    )  # ISO date preferred

    diagnosis: str | None = None
    medicines_prescribed: list[str] = Field(default_factory=list)
    tests_prescribed: list[str] = Field(default_factory=list)
    procedures: list[str] = Field(default_factory=list)


class BillExtraction(BaseExtraction):
    document_type: Literal["bill"] = "bill"

    date: str | None = Field(default=None, validation_alias=AliasChoices("date", "bill_date", "service_date"))
    hospital_name: str | None = Field(default=None, validation_alias=AliasChoices("hospital_name", "provider_name", "hospital", "clinic"))

    consultation_fee: float | None = None
    diagnostic_tests: float | None = None
    medicines: float | None = None
    therapy_charges: float | None = None
    root_canal: float | None = None
    teeth_whitening: float | None = None
    mri_scan: float | None = None
    ct_scan: float | None = None
    other: float | None = None
    total: float | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "total",
            "gross_amount",
            "gross_total",
            "gross",
            "grand_total",
            "net_amount",
            "amount_payable",
        ),
    )

    # Optional richer signals (ignored by deterministic rules, but useful for UI/debug).
    patient_name: str | None = Field(default=None, validation_alias=AliasChoices("patient_name", "patient"))
    bill_number: str | None = Field(default=None, validation_alias=AliasChoices("bill_number", "invoice_number", "bill_no"))
    network_hospital: bool | None = Field(default=None, validation_alias=AliasChoices("network_hospital", "is_network_hospital"))
    payment_mode: str | None = Field(default=None, validation_alias=AliasChoices("payment_mode", "payment_method"))
    line_items: list[dict[str, Any]] = Field(default_factory=list)

    test_names: list[str] = Field(default_factory=list)


class ReportExtraction(BaseExtraction):
    document_type: Literal["report"] = "report"
    date: str | None = Field(default=None, validation_alias=AliasChoices("date", "report_date"))
    test_names: list[str] = Field(default_factory=list)
    summary: str | None = None


class PharmacyBillExtraction(BaseExtraction):
    document_type: Literal["pharmacy_bill"] = "pharmacy_bill"
    date: str | None = Field(default=None, validation_alias=AliasChoices("date", "bill_date", "invoice_date"))
    medicines: list[str] = Field(default_factory=list)
    total: float | None = Field(default=None, validation_alias=AliasChoices("total", "gross_amount", "grand_total", "amount"))


class UnknownExtraction(BaseExtraction):
    document_type: Literal["unknown"] = "unknown"
    raw_text_excerpt: str | None = None


ExtractionModel = PrescriptionExtraction | BillExtraction | ReportExtraction | PharmacyBillExtraction | UnknownExtraction


class MedicalNecessityAssessment(BaseModel):
    is_aligned: bool = True
    rationale: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    mismatch_signals: list[str] = Field(default_factory=list)


class SafeLLMError(BaseModel):
    error: str
    details: dict[str, Any] | None = None


DecisionType = Literal["APPROVED", "REJECTED", "PARTIAL", "MANUAL_REVIEW"]


class FinalDecisionReview(BaseModel):
    recommended_decision: DecisionType = "MANUAL_REVIEW"
    recommended_approved_amount: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    rationale: str = ""
    disagreements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
