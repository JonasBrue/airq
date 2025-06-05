"""
API-Modul des air-Q Backends.

Enthält FastAPI-Router, Schemas und Endpunkt-Definitionen.
"""
from .routes import router
from .schemas import (
    SensorDataSchema,
    SensorDataListResponse, 
    HealthCheckResponse,
    ErrorResponse,
    SensorDataQueryParams
)

__all__ = [
    "router",
    "SensorDataSchema",
    "SensorDataListResponse",
    "HealthCheckResponse", 
    "ErrorResponse",
    "SensorDataQueryParams"
] 