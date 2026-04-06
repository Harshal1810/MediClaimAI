from app.rules.document_validation import validate_required_documents


def test_reports_required_when_tests_indicated():
    claim_context = {
        "claim": {"member_name": "Rajesh Kumar", "treatment_date": "2024-11-01"},
        "documents": {
            "prescription": {"doctor_reg": "KA/45678/2015", "diagnosis": "Viral fever", "patient_name": "Rajesh Kumar"},
            "bill": {"diagnostic_tests": 500, "date": "2024-11-01"},
        },
        "document_types": ["prescription", "bill"],
        "normalized": {"tests": ["CBC"]},
        "ocr_texts": {"prescription": "Patient Name: Rajesh Kumar", "bill": "CBC Test"},
    }
    ok, reason, meta = validate_required_documents(claim_context, policy={})
    assert ok is False
    assert reason == "MISSING_DOCUMENTS"
    assert "missing_report" in (meta.get("flags") or [])


def test_pharmacy_bill_required_when_medicines_indicated():
    claim_context = {
        "claim": {"member_name": "Rajesh Kumar", "treatment_date": "2024-11-01"},
        "documents": {
            "prescription": {"doctor_reg": "KA/45678/2015", "diagnosis": "Viral fever", "patient_name": "Rajesh Kumar", "medicines_prescribed": ["Paracetamol"]},
            "bill": {"pharmacy_total": 140, "date": "2024-11-01"},
        },
        "document_types": ["prescription", "bill"],
        "normalized": {"medicines": ["Paracetamol"]},
        "ocr_texts": {"prescription": "Paracetamol", "bill": "Medicine"},
    }
    ok, reason, meta = validate_required_documents(claim_context, policy={})
    assert ok is False
    assert reason == "MISSING_DOCUMENTS"
    assert "missing_pharmacy_bill" in (meta.get("flags") or [])

