import json
from app.core.config import settings


class PolicyLoader:
    @staticmethod
    def load_policy():
        with open(settings.POLICY_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def load_derived_rules():
        with open(settings.DERIVED_RULES_FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
