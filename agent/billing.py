"""Per-user monthly spend cap on investigations -- lets a user bound how much
their own BYOK AI key can be charged, sitting alongside (not replacing)
loop.py's MAX_COST_PER_RUN single-run guardrail."""
import investigations
import users


def check_budget(user_id: int) -> dict:
    """{"allowed": bool, "spent_usd": float, "limit_usd": float|None}. No
    limit set on the user (None) means unlimited -- always allowed."""
    user = users.get_user_by_id(user_id)
    limit = user.get("monthly_limit_usd") if user else None
    spent = investigations.monthly_cost_usd(user_id)
    return {"allowed": limit is None or spent < limit, "spent_usd": spent, "limit_usd": limit}
