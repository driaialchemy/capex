"""Every code a person might meet has a plain-English label."""

from typing import get_args

from capex.finance import Metrics
from capex.flight_recorder import EventType
from capex.labels import (
    CHECKS_FAILED,
    CHECKS_PASSED,
    EVENT_TYPES,
    LOG_COLUMNS,
    METRICS,
    RECOMMENDATIONS,
    ROLES,
    STATUSES,
)
from capex.schemas import PanelRole, Recommendation
from capex.verifier import _BLOCKING

_STATUSES = ("PENDING_APPROVAL", "BLOCKED", "FINAL", "RETURNED")
_LOG_FIELDS = (
    "ts",
    "event_type",
    "actor",
    "attempt_number",
    "retry_of",
    "retry_reason",
    "status",
    "detail",
)


def test_every_recommendation_status_check_metric_role_and_event_has_a_label():
    for name in get_args(Recommendation):
        assert RECOMMENDATIONS[name]
    for name in _STATUSES:
        assert STATUSES[name]
    for name in _BLOCKING:
        assert CHECKS_PASSED[name]
        assert CHECKS_FAILED[name]
    for name in Metrics.model_fields:
        assert METRICS[name]
    for name in get_args(PanelRole):
        assert ROLES[name]
    assert ROLES["judge"]
    for name in get_args(EventType):
        assert EVENT_TYPES[name]
    for name in _LOG_FIELDS:
        assert LOG_COLUMNS[name]
