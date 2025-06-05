"""
Task-Management für das air-Q Backend.

Dieses Modul verwaltet asynchrone Tasks wie das Sensor-Polling.
"""

from .poller import start_poller, stop_poller

__all__ = ["start_poller", "stop_poller"] 