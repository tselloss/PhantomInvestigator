import pytest

import rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """rate_limit's hit-counters are process-global (see rate_limit.py) --
    without this, tests in this same pytest run that hit /auth/login or
    /webhooks/* repeatedly would trip each other's rate limit depending on
    run order/volume."""
    rate_limit.reset()
    yield
    rate_limit.reset()
