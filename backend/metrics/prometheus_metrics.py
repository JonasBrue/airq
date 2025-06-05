"""
Prometheus-Metriken für air-Q Sensor-Daten.

Dieses Modul definiert und verwaltet Prometheus-Metriken
für die verschiedenen Sensor-Messwerte.
"""

import logging
from typing import Dict, Any, Optional
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Prometheus Metrics Definitionen
temperature_gauge = Gauge(
    'airq_temperature_celsius',
    'Temperatur in Celsius',
    ['sensor_path']
)

humidity_gauge = Gauge(
    'airq_humidity_percent', 
    'Luftfeuchtigkeit in Prozent',
    ['sensor_path']
)

co2_gauge = Gauge(
    'airq_co2_ppm',
    'CO2-Konzentration in ppm', 
    ['sensor_path']
)

# Weitere häufige air-Q Sensoren
pressure_gauge = Gauge(
    'airq_pressure_hpa',
    'Luftdruck in hPa',
    ['sensor_path'] 
)

no2_gauge = Gauge(
    'airq_no2_ppm',
    'NO2-Konzentration in ppm',
    ['sensor_path']
)

tvoc_gauge = Gauge(
    'airq_tvoc_ppb', 
    'TVOC-Konzentration in ppb',
    ['sensor_path']
)

pm25_gauge = Gauge(
    'airq_pm25_ugm3',
    'PM2.5 Feinstaub in µg/m³',
    ['sensor_path']
)

pm10_gauge = Gauge(
    'airq_pm10_ugm3',
    'PM10 Feinstaub in µg/m³', 
    ['sensor_path']
)

sound_gauge = Gauge(
    'airq_sound_db',
    'Geräuschpegel in dB',
    ['sensor_path']
)

# Counter für Anzahl der verarbeiteten Datensätze
sensor_data_total = Counter(
    'airq_sensor_data_total',
    'Gesamtanzahl verarbeiteter Sensor-Datensätze',
    ['sensor_path']
)

# Mapping von Sensor-Namen zu Gauges
SENSOR_METRICS = {
    'temperature': temperature_gauge,
    'humidity': humidity_gauge,
    'co2': co2_gauge,
    'pressure': pressure_gauge,
    'no2': no2_gauge,
    'tvoc': tvoc_gauge,
    'pm2_5': pm25_gauge,  # air-Q verwendet oft pm2_5 statt pm25
    'pm10': pm10_gauge,
    'sound': sound_gauge,
}


def extract_sensor_value(sensor_data: Any) -> Optional[float]:
    """
    Extrahiert den Sensor-Wert aus air-Q Datenformat.
    
    air-Q gibt oft [Wert, Fehler] Arrays zurück.
    
    Args:
        sensor_data: Rohdaten vom Sensor
        
    Returns:
        Extrahierter Zahlenwert oder None
    """
    if sensor_data is None:
        return None
        
    if isinstance(sensor_data, list) and len(sensor_data) > 0:
        # Erstes Element ist der Messwert
        return float(sensor_data[0]) if sensor_data[0] is not None else None
    elif isinstance(sensor_data, (int, float)):
        return float(sensor_data)
    else:
        logger.warning(f"Unbekanntes Sensor-Datenformat: {type(sensor_data)}")
        return None


def update_sensor_metrics(sensor_path: str, decoded_data: Dict[str, Any]) -> None:
    """
    Aktualisiert alle verfügbaren Prometheus-Metriken mit neuen Sensor-Daten.
    
    Args:
        sensor_path: Pfad/Identifikator des Sensors
        decoded_data: Entschlüsselte Sensor-Daten
    """
    logger.debug(f"Aktualisiere Metriken für Sensor {sensor_path}")
    
    # Counter incrementieren
    sensor_data_total.labels(sensor_path=sensor_path).inc()
    
    # Alle verfügbaren Sensor-Werte durchgehen
    for sensor_key, gauge in SENSOR_METRICS.items():
        if sensor_key in decoded_data:
            value = extract_sensor_value(decoded_data[sensor_key])
            if value is not None:
                gauge.labels(sensor_path=sensor_path).set(value)
                logger.debug(f"Setze {sensor_key} = {value} für {sensor_path}")
    
    logger.debug(f"Metriken-Update für {sensor_path} abgeschlossen")


def get_prometheus_metrics() -> str:
    """
    Generiert die Prometheus-Metriken im Text-Format.
    
    Returns:
        Prometheus-Metriken als String
    """
    return generate_latest()


def get_content_type() -> str:
    """
    Gibt den Content-Type für Prometheus-Metriken zurück.
    
    Returns:
        MIME-Type für Prometheus-Metriken
    """
    return CONTENT_TYPE_LATEST 