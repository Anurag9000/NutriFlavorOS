from __future__ import annotations

from backend.main import app


def test_production_app_mounts_preparation_operations_routes():
    observed = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    expected = {
        (
            "/api/v1/households/{household_id}/preparation-operations/resource-calendars",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/resource-calendars",
            "GET",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/resource-calendars/{calendar_id}",
            "GET",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules",
            "GET",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}",
            "GET",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/approve",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/complete",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/cancel",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/invalidate",
            "POST",
        ),
        (
            "/api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/events",
            "GET",
        ),
    }
    assert expected <= observed
