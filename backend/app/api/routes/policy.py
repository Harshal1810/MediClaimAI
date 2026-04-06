from fastapi import APIRouter
from app.services.policy_loader import PolicyLoader

router = APIRouter(tags=["Policy"])


@router.get("/policy")
def get_policy():
    return {"policy": PolicyLoader.load_policy(), "derived_rules": PolicyLoader.load_derived_rules()}
