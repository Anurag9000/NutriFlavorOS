"""NutriFlavorOS backend package."""

# Import additive ORM mappings during package initialization so every process
# using Base.metadata sees the complete reviewed schema regardless of which
# service module is imported first.
from backend import household_plan_lifecycle_models as _household_plan_lifecycle_models
from backend import preparation_task_execution_models as _preparation_task_execution_models

__all__ = []
