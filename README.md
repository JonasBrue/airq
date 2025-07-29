# air-Q Luftqualitätssensor

Ein vollständiges System für die Sammlung, Verarbeitung und Visualisierung von air-Q Luftqualitätssensor-Daten mit MCP Integration.

## 🌟 Überblick

Dieses Projekt ermöglicht den sicheren Zugriff auf Daten von air-Q-Sensoren, deren kontinuierliche Sammlung und Aufbereitung sowie die Bereitstellung über eine moderne REST-API und MCP Integration. Das System unterstützt Echtzeitmonitoring, historische Datenanalyse und automatisierte Berichtserstellung.

### Hauptfunktionen

- ✅ **Automatisches Polling**: Kontinuierliche Datensammlung von konfigurierten air-Q Sensoren
- 🔐 **Sichere Entschlüsselung**: Verarbeitung verschlüsselter air-Q Sensordaten
- 📊 **REST API**: Flexible Abfrage- und Filtermöglichkeiten für Sensordaten
- 📄 **PDF-Berichte**: Automatische Generierung umfassender Luftqualitäts-Berichte
- 🤖 **MCP Server**: MCP Integration für natürliche Sprachabfragen
- 📈 **Monitoring**: Prometheus-Metriken und Grafana-Dashboards
- 🚨 **Telegram Alerts**: Automatische Benachrichtigungen bei kritischen Luftqualitätswerten
- 🗄️ **Datenspeicherung**: Robuste PostgreSQL-Datenbank mit optimierten Indizes
- 🐳 **Container-Ready**: Vollständige Docker-Compose-Umgebung

## 🏗️ Architektur

```
                        ┌─────────────────┐               
                        │   MCP Server    │───▶ z.B. Claude Desktop
                        │ (API Interface) │     (Chat Interface)
                        └─────────────────┘               
                              │                       
                              ▼                       
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
- **Conda/Anaconda** für MCP Server (optional)
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
   
   # Telegram Alerting (optional)
   TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890
   TELEGRAM_CHAT_ID=123456789
   HEALTH_ALERT_THRESHOLD=600
   ALERT_COOLDOWN_MINUTES=30
   MIN_CONSECUTIVE_POLLS=10
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
- **PDF-Bericht generieren**: http://localhost:8000/report
- **Grafana Dashboard**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090
- **Health Check**: http://localhost:8000/sensors/health

## 🤖 MCP Server

Der air-Q MCP Server ermöglicht es, Sensordaten direkt über z.B. Claude Desktop in natürlicher Sprache abzufragen.

### MCP Server Installation

1. **Backend starten** (falls noch nicht gestartet)
   ```bash
   docker-compose up -d
   ```

2. **Conda Environment erstellen** (falls noch nicht vorhanden)
   ```bash
   conda env create -f backend/environment.yml
   ```

3. **Environment aktivieren und MCP Server installieren**
   ```bash
   conda activate airq
   mcp install mcp_server.py
   ```

### Verfügbare Befehle

Der MCP Server stellt folgende Tools bereit:

- **`get_available_sensors`**: Listet alle verfügbaren air-Q Sensoren auf
- **`get_sensor_data`**: Ruft aktuelle Sensordaten ab (mit Filtern)
- **`get_sensor_summary`**: Detaillierte Statistiken für einen spezifischen Sensor
- **`get_health_status`**: Überprüft den Systemstatus
- **`start_backend`**: Anweisungen zum Backend-Start

### Beispiel-Verwendung in Claude Desktop

```
Du: "Zeige mir die verfügbaren Sensoren"
Claude: Verwendet get_available_sensors()

Du: "Wie ist die aktuelle Luftqualität bei Sensor 1?"
Claude: Verwendet get_sensor_data(sensor_path="/airq/1")

Du: "Gib mir eine Zusammenfassung für Sensor /airq/1"
Claude: Verwendet get_sensor_summary(sensor_path="/airq/1")
```

### MCP Server entwickeln/debuggen

```bash
# Entwicklungsmodus starten
mcp dev mcp_server.py

# Server-URL: http://localhost:6274
```

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

## 📄 PDF-Berichte

Das System kann automatisch umfassende PDF-Berichte mit Luftqualitätsdaten, Statistiken und Zeitreihen-Diagrammen erstellen.

### PDF-Bericht generieren

```bash
http://localhost:8000/report
```

### Berichtsinhalte

Die generierten PDF-Berichte enthalten:

- **Übersichtsseite**:
  - Sensor-Übersicht mit aktuellen Messwerten
  - Gesamtstatistiken aller Sensoren
  - Zeitreihen-Diagramme der wichtigsten Metriken

- **Detailseiten für jeden Sensor**:
  - Umfassende Statistiken (Durchschnitt, Minimum, Maximum, Standardabweichung)
  - Minutenweise aggregierte Messwerte der letzten 15 Minuten
  - Einzelne Zeitreihen-Diagramme für alle verfügbaren Metriken

- **Visualisierungen**:
  - Zeitreihen-Charts für alle Luftqualitäts-Metriken
  - Übersichtsgrafiken und Detailansichten (letzte 24 Stunden)
  - Professionelle Formatierung mit Logos

### Unterstützte Metriken

Die PDF-Berichte dokumentieren automatisch alle verfügbaren Sensordaten.

### Automatische Features

- **Zeitzonenkonvertierung**: Alle Zeitstempel werden automatisch in Berliner Zeit (MEZ/MESZ) angezeigt
- **Datenperiode**: Berichte enthalten standardmäßig die letzten 30 Tage Sensordaten
- **Multi-Sensor-Support**: Automatische Erkennung und separate Auswertung aller konfigurierten Sensoren
- **Statistische Auswertung**: Durchschnitt, Minimum, Maximum und Standardabweichung für alle Metriken
- **Aktuelle Werte**: Minutenweise aggregierte Messwerte der letzten 15 Minuten
- **Professionelles Layout**: Inklusive Organisation-Logos und strukturiertem Design

### Entwicklung

Die PDF-Generierung nutzt folgende Technologien:

- **ReportLab**: PDF-Erstellung und Layout
- **Matplotlib**: Zeitreihen-Diagramme und Visualisierungen
- **NumPy**: Statistische Berechnungen
- **SVGlib**: Logo-Integration für professionelles Branding

## 📊 Monitoring und Dashboards

### Grafana Dashboard

Das vorkonfigurierte Grafana-Dashboard zeigt:

- **Echtzeit-Übersicht**: Temperatur, Luftfeuchtigkeit, CO2, Luftdruck
- **Zeitreihen-Diagramme**: Historische Verläufe aller Sensoren
- **Luftqualitäts-Indikatoren**: PM1, PM2.5, PM10, TVOC, NO2
- **Gesundheitsindex**: air-Q Gesundheitsbewertung
- **System-Metriken**: Datenverarbeitungsraten und Status

### Branding

In der kostenlosen Edition sind nur begrenzte Anpassungen möglich:

- **Organisation-Name**: Änderbar über die Grafana-Einstellungen
- **Dashboard-Titel**: Individuelle Dashboard-Namen
- **Benutzer-Profile**: Anpassbare Benutzer-Namen und -Einstellungen
- **Zeitzone**: Benutzer-spezifische Zeitzone-Einstellungen

## 🚨 Telegram Alerts

Das System kann automatisch Benachrichtigungen über Telegram senden, wenn der Gesundheitsindex unter einen kritischen Wert fällt.

### Telegram Bot einrichten

1. **Bot erstellen**
   - Schreibe eine Nachricht an [@BotFather](https://t.me/BotFather)
   - Sende `/newbot` und folge den Anweisungen
   - Notiere dir den Bot-Token

2. **Chat-ID ermitteln**
   - Schreibe eine Nachricht an deinen Bot
   - Schreibe eine Nachricht an [@userinfobot](https://t.me/userinfobot)
   - Notiere dir deine Chat-ID

3. **Konfiguration**
   ```env
   TELEGRAM_BOT_TOKEN=dein_bot_token
   TELEGRAM_CHAT_ID=deine_chat_id
   HEALTH_ALERT_THRESHOLD=600
   ALERT_COOLDOWN_MINUTES=30
   MIN_CONSECUTIVE_POLLS=10
   ```

### Alert-Funktionen

- **Warnung**: Benachrichtigung wenn Gesundheitsindex unter Schwellenwert fällt
- **Entwarnung**: Automatische Nachricht wenn sich die Luftqualität wieder verbessert
- **Rate Limiting**: Verhindert Spam durch Cooldown-Perioden (Standard: 30 Minuten)
- **Konsekutive Messwerte**: Erfordert mehrere aufeinanderfolgende niedrige Werte bevor Alert gesendet wird (Standard: 10 Polls)
- **Markdown-Formatierung**: Übersichtliche Darstellung mit Emojis und Formatierung

### Konfigurationsmöglichkeiten

- **`HEALTH_ALERT_THRESHOLD`**: Schwellenwert für den Gesundheitsindex (Standard: 100)
- **`ALERT_COOLDOWN_MINUTES`**: Wartezeit zwischen gleichartigen Alerts (Standard: 30 Minuten)
- **`MIN_CONSECUTIVE_POLLS`**: Anzahl aufeinanderfolgender niedriger Messwerte bevor Alert gesendet wird (Standard: 10)

Das System verhindert Fehlalarme durch einzelne Ausreißer-Werte, indem es nur nach mehreren konsekutiven niedrigen Messwerten einen Alert sendet. Sobald ein Messwert wieder über dem Schwellenwert liegt, wird der Zähler zurückgesetzt.

### Beispiel-Nachricht

```
🚨 Luftqualitäts-Warnung

Sensor: /livingroom
Gesundheitsindex: 485/1000
Schwellenwert: 600

Die Luftqualität ist nach 10 konsekutiven Messungen unter den kritischen Wert gefallen!
```

## ⚙️ Konfiguration

### Umgebungsvariablen

| Variable | Beschreibung | Standard | Beispiel |
|----------|-------------|----------|----------|
| `AIRQ_HOST` | IP-Adresse des air-Q Sensors | - | `192.168.1.100` |
| `AIRQ_PASSWORD` | Entschlüsselungspasswort | - | `airqsetup` |
| `AIRQ_SENSORS` | Komma-getrennte Sensor-Pfade | - | `/living,/bedroom` |
| `POLL_INTERVAL_SECONDS` | Polling-Intervall | `1.5` | `1.5` |
| `DATABASE_URL` | PostgreSQL-Verbindung | Auto | `postgresql+asyncpg://...` |
| `LOG_LEVEL` | Log-Level | `INFO` | `DEBUG` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token (optional) | - | `1234567890:ABC...` |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID (optional) | - | `123456789` |
| `HEALTH_ALERT_THRESHOLD` | Gesundheitsindex-Schwellenwert | `600` | `600` |
| `ALERT_COOLDOWN_MINUTES` | Alert-Cooldown in Minuten | `30` | `30` |
| `MIN_CONSECUTIVE_POLLS` | Minimale Anzahl aufeinanderfolgender Polls für einen Alarm | `10` | `10` |

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

4. **MCP Server testen**
   ```bash
   mcp dev mcp_server.py
   ```

### Code-Struktur

```
backend/
├── main.py              # FastAPI Anwendung
├── config.py            # Konfiguration
├── Dockerfile           # Container-Definition
├── environment.yml      # Conda Environment
├── api/                 # API Routen und Schemas
│   ├── routes.py
│   └── schemas.py
├── db/                  # Datenbank Models
│   ├── database.py
│   └── models.py
├── metrics/             # Prometheus Metriken
│   └── prometheus_metrics.py
├── reports/             # PDF Reports
│   └── pdf_generator.py
└── task/                # Background Tasks
    ├── config.py
    ├── notifications.py
    └── poller.py

monitoring/
├── grafana/             # Grafana Konfiguration
│   ├── dashboards/      # Dashboard-Definitionen (JSON)
│   │   └── airq-dashboard.json
│   └── provisioning/    # Automatische Konfiguration
│       ├── dashboards/  # Dashboard-Provider
│       │   └── dashboard-provider.yml
│       └── datasources/ # Datenquellen-Konfiguration
│           └── prometheus.yml
└── prometheus.yml       # Prometheus Konfiguration

mcp_server.py            # MCP Server Integration
docker-compose.yml       # Container Orchestrierung
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
