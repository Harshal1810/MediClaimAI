class NormalizationService:
    SERVICE_MAP = {
        "consultation fee": "consultation",
        "doctor consultation": "consultation",
        "cbc": "diagnostic_tests",
        "complete blood count": "diagnostic_tests",
        "mri": "diagnostic_tests",
        "root canal": "dental",
        "teeth whitening": "cosmetic_dental",
        "ayurveda": "alternative_medicine",
        "glasses": "vision",
    }

    def normalize_extracted_data(self, extracted_docs: list[dict]) -> dict:
        normalized = {
            "diagnosis": None,
            "services": [],
            "tests": [],
            "procedures": [],
            "medicines": [],
            "line_items": [],
            "documents": {},
        }
        for doc in extracted_docs:
            extracted = doc.get("extracted") or {}
            doc_type = (extracted.get("document_type") or doc.get("document_type") or "unknown").lower()
            normalized["documents"][doc_type] = extracted
            if not normalized["diagnosis"] and extracted.get("diagnosis"):
                normalized["diagnosis"] = extracted.get("diagnosis")
            if extracted.get("tests_prescribed"):
                normalized["tests"].extend(extracted.get("tests_prescribed") or [])
            if extracted.get("medicines_prescribed"):
                normalized["medicines"].extend(extracted.get("medicines_prescribed") or [])

            # LLM extractions commonly use these keys.
            if extracted.get("test_names"):
                normalized["tests"].extend(extracted.get("test_names") or [])
            if extracted.get("tests"):
                normalized["tests"].extend(extracted.get("tests") or [])
            if extracted.get("medicines"):
                if isinstance(extracted.get("medicines"), list):
                    normalized["medicines"].extend(extracted.get("medicines") or [])

        normalized["tests"] = sorted(set([str(t) for t in normalized["tests"] if t]))
        normalized["medicines"] = sorted(set([str(m) for m in normalized["medicines"] if m]))
        return normalized
