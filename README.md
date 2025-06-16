# air-Q Luftqualitätssensor

Ein vollständiges System für die Sammlung, Verarbeitung und Visualisierung von air-Q Luftqualitätssensor-Daten.

## 🌟 Überblick

Dieses Projekt ermöglicht den sicheren Zugriff auf Daten von air-Q-Sensoren, deren kontinuierliche Sammlung und Aufbereitung sowie die Bereitstellung über eine moderne REST-API. Das System unterstützt Echtzeitmonitoring, historische Datenanalyse und automatisierte Berichtserstellung.

### Hauptfunktionen

- ✅ **Automatisches Polling**: Kontinuierliche Datensammlung von konfigurierten air-Q Sensoren
- 🔐 **Sichere Entschlüsselung**: Verarbeitung verschlüsselter air-Q Sensordaten
- 📊 **REST API**: Flexible Abfrage- und Filtermöglichkeiten für Sensordaten
- 📈 **Monitoring**: Prometheus-Metriken und Grafana-Dashboards
- 🗄️ **Datenspeicherung**: Robuste PostgreSQL-Datenbank mit optimierten Indizes
- 🐳 **Container-Ready**: Vollständige Docker-Compose-Umgebung

## 🏗️ Architektur

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   air-Q Sensor  │───▶│  Backend API     │───▶│   PostgreSQL    │
│  (verschlüsselt)│     │  (FastAPI)      │     │   Datenbank     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                              │
                              ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   Prometheus    │───▶│     Grafana     │
                        │   (Metriken)    │     │ (Visualisierung)│
                        └─────────────────┘     └─────────────────┘
```

### Komponenten

- **Backend API** (Port 8000): FastAPI-basierte REST-API für Datenzugriff
- **PostgreSQL** (Port 5432): Datenbank für Sensordaten-Speicherung
- **Prometheus** (Port 9090): Metriken-Sammlung und -Speicherung
- **Grafana** (Port 3000): Dashboard und Visualisierung

## 🚀 Schnellstart

### Voraussetzungen

- **Docker** und **Docker Compose**
- **Git** für Repository-Klonen
- Zugang zu einem air-Q Sensor im Netzwerk

### Installation

1. **Repository klonen**
   ```bash
   git clone <repository-url>
   cd airq
   ```

2. **Umgebungsvariablen konfigurieren** (Bearbeiten Sie die `.env` Datei)
   ```env
   AIRQ_HOST=123.456.789.0              # IP-Adresse Ihres air-Q Sensors
   AIRQ_PASSWORD=ihr_airq_passwort      # air-Q Entschlüsselungspasswort
   AIRQ_SENSORS=/livingroom,/bedroom    # Komma-getrennte Sensor-Pfade
   ```

3. **System starten**
   ```bash
   docker-compose up -d
   ```

4. **Services überprüfen**
   ```bash
   docker-compose ps
   ```

### Erste Schritte

Nach dem Start können Sie die Services unter folgenden URLs erreichen:

- **API Dokumentation**: http://localhost:8000/docs
- **Grafana Dashboard**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Health Check**: http://localhost:8000/sensors/health

## 📡 API Verwendung

### Aktuelle Sensordaten abrufen

```bash
curl "http://localhost:8000/sensors/?limit=10"
```

### Daten filtern

```bash
# Nach Sensor-Pfad filtern
curl "http://localhost:8000/sensors/?limit=100&offset=0&sensor_path=%2Fairq%2F1"
```

### Verfügbare Sensoren auflisten

```bash
curl "http://localhost:8000/sensors/sensors"
```

## 📊 Monitoring und Dashboards

### Grafana Dashboard

Das vorkonfigurierte Grafana-Dashboard zeigt:

- **Echtzeit-Übersicht**: Temperatur, Luftfeuchtigkeit, CO2, Luftdruck
- **Zeitreihen-Diagramme**: Historische Verläufe aller Sensoren
- **Luftqualitäts-Indikatoren**: PM1, PM2.5, PM10, TVOC, NO2
- **Gesundheitsindex**: air-Q Gesundheitsbewertung
- **System-Metriken**: Datenverarbeitungsraten und Status

## ⚙️ Konfiguration

### Umgebungsvariablen

| Variable | Beschreibung | Standard | Beispiel |
|----------|-------------|----------|----------|
| `AIRQ_HOST` | IP-Adresse des air-Q Sensors | - | `192.168.1.100` |
| `AIRQ_PASSWORD` | Entschlüsselungspasswort | - | `airqsetup` |
| `AIRQ_SENSORS` | Komma-getrennte Sensor-Pfade | - | `/living,/bedroom` |
| `POLL_INTERVAL_SECONDS` | Polling-Intervall | `1.5` | `2.0` |
| `DATABASE_URL` | PostgreSQL-Verbindung | Auto | `postgresql+asyncpg://...` |
| `LOG_LEVEL` | Log-Level | `INFO` | `DEBUG` |

## 🔧 Entwicklung

### Lokale Entwicklung ohne Docker

1. **Conda-Umgebung erstellen**
   ```bash
   conda env create -f backend/environment.yml
   conda activate airq
   ```

2. **PostgreSQL starten**
   ```bash
   docker run -d -p 5432:5432 -e POSTGRES_USER=airq -e POSTGRES_PASSWORD=airq -e POSTGRES_DB=airq postgres:15-alpine
   ```

3. **Backend starten**
   ```bash
   cd backend
   python main.py
   ```

### Code-Struktur

```
backend/
├── main.py              # FastAPI Anwendung
├── config.py            # Konfiguration
├── api/                 # API Routen und Schemas
│   ├── routes.py
│   └── schemas.py
├── db/                  # Datenbank Models
│   ├── database.py
│   └── models.py
├── task/                # Background Tasks
│   └── poller.py
└── metrics/             # Prometheus Metriken
    └── prometheus_metrics.py
```

### Testing

```bash
# API Tests
curl -X GET "http://localhost:8000/sensors/health"
```

## 📋 Unterstützte Sensoren

Das System unterstützt alle air-Q Sensoren und Messwerte:

### Grundmessungen
- **Temperatur** (°C) - Raumtemperatur
- **Luftfeuchtigkeit** (%) - Relative und absolute Feuchtigkeit
- **Luftdruck** (hPa) - Absoluter Druck
- **Taupunkt** (°C) - Kondensationstemperatur

### Gaskonzentrationen
- **CO2** (ppm) - Kohlendioxid
- **CO** (mg/m³) - Kohlenmonoxid
- **NO2** (µg/m³) - Stickstoffdioxid
- **O3** (µg/m³) - Ozon
- **TVOC** (ppb) - Flüchtige organische Verbindungen
- **H2S** (µg/m³) - Schwefelwasserstoff

### Partikel
- **PM1, PM2.5, PM10** (µg/m³) - Feinstaub-Konzentrationen
- **Partikelgröße** (µm) - Durchschnittliche Größe

### Weitere
- **Sauerstoff** (Vol-%) - O2-Konzentration
- **Geräuschpegel** (dB) - Lärmmessung
- **Gesundheitsindex** (0-1000) - air-Q Bewertung

## 🚨 Troubleshooting

### Häufige Probleme

**Sensor nicht erreichbar**
```bash
# Verbindung testen
ping 123.456.789.0
curl http://123.456.789.0/ping
```

**Entschlüsselungsfehler**
- Überprüfen Sie das `AIRQ_PASSWORD`
- Standard-Passwort: `airqsetup`

**Container starten nicht**
```bash
# Logs überprüfen
docker-compose logs backend
docker-compose logs db
```

**Keine Daten in Grafana**
- Überprüfen Sie Prometheus unter http://localhost:9090/targets
- Backend-Metriken: http://localhost:8000/metrics

### Log-Level erhöhen

```env
LOG_LEVEL=DEBUG
```

## 📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Siehe [LICENSE](LICENSE) für Details.

---

**Viel Erfolg beim Monitoring Ihrer Luftqualität! 🌬️📊**
