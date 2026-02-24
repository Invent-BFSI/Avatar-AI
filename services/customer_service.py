# services/customer_service.py

def build_profile_from_conversation(conv: dict) -> dict:
    """
    Map your conversation payload to the DB schema keys expected by the proc.
    Adjust the mapping if your incoming keys differ (camelCase vs snake_case).
    """
    return {
        "customer_id": conv["customer_id"],
        "first_name": conv.get("first_name"),
        "last_name": conv.get("last_name"),
        "account_type": conv.get("account_type"),
        "customer_type": conv.get("customer_type"),
        "address": conv.get("address"),
        "phone_number": conv.get("phone_number"),
        "ssn_masked": conv.get("ssn_masked"),
        "portfolio_status": conv.get("portfolio_status"),
        "relationships": conv.get("relationships"),
        "retail_banking_product": conv.get("retail_banking_product"),
        "email_id": conv.get("email_id"),
        "monthly_inflow": conv.get("monthly_inflow"),
        "monthly_outflow": conv.get("monthly_outflow"),
        "total_debt": conv.get("total_debt"),
        "risk_appetite": conv.get("risk_appetite"),
        "preferred_sector": conv.get("preferred_sector"),
        "investment_amount": conv.get("investment_amount"),
        "investment_period": conv.get("investment_period"),
        "future_goals": conv.get("future_goals"),
    }
