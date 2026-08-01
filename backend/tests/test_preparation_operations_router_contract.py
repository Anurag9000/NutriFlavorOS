from __future__ import annotations

from fastapi import FastAPI

from backend.api import preparation_operations_routes


def test_preparation_operations_router_declares_expected_methods():
    app = FastAPI()
    app.include_router(preparation_operations_routes.router)
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
