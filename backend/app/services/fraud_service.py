class FraudService:
    def analyze(self, claim_context: dict) -> dict:
        return {"manual_review": False, "flags": [], "confidence": 0.95}
