"""
Reports-Modul für das air-Q Backend.

Enthält PDF-Report-Generator und andere Berichtsfunktionen.
"""

from .pdf_generator import AirQualityPDFGenerator

__all__ = [
    "AirQualityPDFGenerator"
] 