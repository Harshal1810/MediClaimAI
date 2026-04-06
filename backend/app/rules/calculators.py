def apply_consultation_copay(amount: float, policy: dict) -> tuple[float, float]:
    copay_percent = policy["coverage_details"]["consultation_fees"]["copay_percentage"]
    deduction = amount * copay_percent / 100
    return amount - deduction, deduction


def apply_network_discount(amount: float, policy: dict) -> tuple[float, float]:
    discount_percent = policy["coverage_details"]["consultation_fees"]["network_discount"]
    discount = amount * discount_percent / 100
    return amount - discount, discount


def apply_percentage_deduction(amount: float, percent: float) -> tuple[float, float]:
    deduction = amount * percent / 100
    return amount - deduction, deduction
