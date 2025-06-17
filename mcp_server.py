# api.py
"""
air-Q MCP Server der die Backend API über HTTP verwendet.
Verwendet die bereits laufenden FastAPI-Endpunkte.
"""

import httpx
from datetime import datetime, timedelta
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("air-Q Sensor MCP-Server")

# Backend API Base URL
API_BASE_URL = "http://localhost:8000"

def format_berlin_time(utc_timestamp: str) -> str:
    """
    Einfache Konvertierung von UTC zu Berliner Zeit.
    
    Args:
        utc_timestamp: UTC-Zeitstempel als String
    
    Returns:
        Formatierter Berliner Zeit-String
    """
    try:
        # Zeitstempel bereinigen
        timestamp_str = utc_timestamp.strip()
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1]
        
        # Parse UTC Zeit
        utc_dt = datetime.fromisoformat(timestamp_str)
        
        # Berliner Zeit = UTC + 1 oder UTC + 2 (je nach Jahreszeit)
        # Juni = Sommerzeit = UTC + 2
        month = utc_dt.month
        
        if 4 <= month <= 9:  # April bis September = Sommerzeit
            berlin_dt = utc_dt + timedelta(hours=2)
            timezone_name = "MESZ"
        else:  # Oktober bis März = Winterzeit
            berlin_dt = utc_dt + timedelta(hours=1)
            timezone_name = "MEZ"
        
        return f"{berlin_dt.strftime('%d.%m.%Y %H:%M:%S')} {timezone_name}"
    
    except:
        # Fallback: Original-Zeitstempel
        return utc_timestamp

@mcp.tool()
async def get_sensor_data(
    limit: int = 10,
    sensor_path: Optional[str] = None,
    since_hours: Optional[int] = None
) -> str:
    """
    Ruft aktuelle Sensordaten vom air-Q Backend ab.
    
    Args:
        limit: Maximale Anzahl Datensätze (Standard: 10, max: 100)
        sensor_path: Spezifischer Sensor-Pfad (z.B. "/airq/1")  
        since_hours: Nur Daten der letzten X Stunden
    
    Returns:
        Formatierte Sensordaten vom Backend
    """
    try:
        # Parameter für API-Request vorbereiten
        params = {"limit": min(limit, 100)}
        
        if sensor_path:
            params["sensor_path"] = sensor_path
            
        # since_hours in ISO timestamp umwandeln (vereinfacht für jetzt)
        # In einer vollständigen Version würde man datetime verwenden
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_BASE_URL}/sensors/", params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                if not data:
                    return "Keine Sensordaten gefunden."
                
                # Formatierte Ausgabe erstellen
                output = f"📊 air-Q Sensordaten (letzte {len(data)} Einträge):\n\n"
                
                for item in data:
                    output += f"🔍 Sensor: {item['sensor_path']}\n"
                    # Berliner Zeit anzeigen
                    berlin_time = format_berlin_time(item['ts_collected'])
                    output += f"⏰ Zeit: {berlin_time}\n"
                    
                    # Wichtige Messwerte extrahieren
                    decoded = item.get('decoded_data', {})
                    if decoded:
                        if 'temperature' in decoded:
                            temp = decoded['temperature'][0] if isinstance(decoded['temperature'], list) else decoded['temperature']
                            output += f"🌡️  Temperatur: {temp:.1f}°C\n"
                        
                        if 'humidity' in decoded:
                            humidity = decoded['humidity'][0] if isinstance(decoded['humidity'], list) else decoded['humidity']
                            output += f"💧 Luftfeuchtigkeit: {humidity:.1f}%\n"
                        
                        if 'co2' in decoded:
                            co2 = decoded['co2'][0] if isinstance(decoded['co2'], list) else decoded['co2']
                            output += f"🌬️  CO2: {co2:.0f} ppm\n"
                            
                        if 'pressure' in decoded:
                            pressure = decoded['pressure'][0] if isinstance(decoded['pressure'], list) else decoded['pressure']
                            output += f"📊 Luftdruck: {pressure:.1f} hPa\n"
                            
                        if 'pm2_5' in decoded:
                            pm25 = decoded['pm2_5'][0] if isinstance(decoded['pm2_5'], list) else decoded['pm2_5']
                            output += f"🫁 PM2.5: {pm25:.1f} µg/m³\n"
                            
                        if 'health' in decoded:
                            health = decoded['health'][0] if isinstance(decoded['health'], list) else decoded['health']
                            output += f"💚 Gesundheitsindex: {health:.0f}\n"
                    
                    output += "─" * 40 + "\n\n"
                
                return output
            
            elif response.status_code == 500:
                return "❌ Backend-Server-Fehler. Ist das air-Q Backend gestartet?"
            else:
                return f"❌ API-Fehler: HTTP {response.status_code}"
                
    except httpx.ConnectError:
        return "❌ Verbindung zum Backend fehlgeschlagen. Ist das air-Q Backend unter http://localhost:8000 erreichbar?"
    except httpx.TimeoutException:
        return "❌ Timeout beim Backend-Request. Das Backend antwortet nicht rechtzeitig."
    except Exception as e:
        return f"❌ Unerwarteter Fehler: {str(e)}"

@mcp.tool()
async def get_available_sensors() -> str:
    """
    Listet alle verfügbaren air-Q Sensoren über die Backend API auf.
    
    Returns:
        Liste aller verfügbaren Sensor-Pfade vom Backend
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_BASE_URL}/sensors/sensors")
            
            if response.status_code == 200:
                sensors = response.json()
                
                if not sensors:
                    return "Keine Sensoren gefunden."
                
                output = "📡 Verfügbare air-Q Sensoren:\n\n"
                
                for sensor_path in sensors:
                    output += f"🔍 Sensor: {sensor_path}\n"
                    
                    # Zusätzliche Info für jeden Sensor abrufen (letzte Daten)
                    try:
                        sensor_response = await client.get(
                            f"{API_BASE_URL}/sensors/", 
                            params={"sensor_path": sensor_path, "limit": 1}
                        )
                        if sensor_response.status_code == 200:
                            sensor_data = sensor_response.json()
                            if sensor_data:
                                berlin_time = format_berlin_time(sensor_data[0]['ts_collected'])
                                output += f"⏰ Letztes Update: {berlin_time}\n"
                    except:
                        pass  # Ignoriere Fehler bei zusätzlichen Infos
                    
                    output += "─" * 30 + "\n\n"
                
                output += f"✅ Insgesamt {len(sensors)} Sensoren gefunden!!!"
                return output
            
            elif response.status_code == 500:
                return "❌ Backend-Server-Fehler. Ist das air-Q Backend gestartet?"
            else:
                return f"❌ API-Fehler: HTTP {response.status_code}"
                
    except httpx.ConnectError:
        return "❌ Verbindung zum Backend fehlgeschlagen. Ist das air-Q Backend unter http://localhost:8000 erreichbar?"
    except httpx.TimeoutException:
        return "❌ Timeout beim Backend-Request."
    except Exception as e:
        return f"❌ Unerwarteter Fehler: {str(e)}"

@mcp.tool()
async def get_health_status() -> str:
    """
    Überprüft den Gesundheitsstatus des air-Q Systems über die Backend API.
    
    Returns:
        Health-Status vom Backend
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_BASE_URL}/sensors/health")
            
            if response.status_code == 200:
                health_data = response.json()
                
                output = "🏥 air-Q System Health Status\n\n"
                
                # Status vom Backend formatieren
                status = health_data.get('status', 'unknown')
                if status == 'healthy':
                    output += "✅ Backend-Status: HEALTHY\n"
                elif status == 'degraded':
                    output += "⚠️  Backend-Status: DEGRADED\n"
                else:
                    output += f"❓ Backend-Status: {status.upper()}\n"
                
                # Timestamp in Berliner Zeit
                timestamp = health_data.get('timestamp')
                if timestamp:
                    berlin_time = format_berlin_time(timestamp)
                    output += f"⏰ Health-Check Zeit: {berlin_time}\n"
                
                # Datenbankstatus
                db_connected = health_data.get('database_connected', False)
                if db_connected:
                    output += "✅ Datenbank: Verbunden\n"
                else:
                    output += "❌ Datenbank: Nicht verbunden\n"
                
                output += "\n📋 Backend API:\n"
                output += f"🌐 Endpunkt: {API_BASE_URL}\n"
                output += "🔗 Verbindung: Erfolgreich\n"
                
                if status == 'healthy' and db_connected:
                    output += "\n🎉 Gesamtstatus: HEALTHY ✅"
                elif db_connected:
                    output += "\n⚠️  Gesamtstatus: DEGRADED 🟡"
                else:
                    output += "\n💥 Gesamtstatus: CRITICAL ❌"
                
                return output
            
            elif response.status_code == 500:
                return "❌ Backend-Health-Check fehlgeschlagen. Server-Fehler."
            else:
                return f"❌ Health-Check API-Fehler: HTTP {response.status_code}"
                
    except httpx.ConnectError:
        return f"❌ Backend nicht erreichbar!\n\n🚨 Das air-Q Backend ist nicht gestartet oder nicht unter {API_BASE_URL} erreichbar.\n\nBitte starte das Backend mit:\ndocker-compose up -d"
    except httpx.TimeoutException:
        return "❌ Health-Check Timeout. Backend antwortet nicht."
    except Exception as e:
        return f"❌ Health-Check Fehler: {str(e)}"

@mcp.tool()
async def get_sensor_summary(sensor_path: str) -> str:
    """
    Gibt eine detaillierte Zusammenfassung für einen spezifischen Sensor über die Backend API.
    
    Args:
        sensor_path: Pfad des Sensors (z.B. "/airq/1")
    
    Returns:
        Detaillierte Statistiken vom Backend für den Sensor
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Aktuelle Daten abrufen
            response = await client.get(
                f"{API_BASE_URL}/sensors/", 
                params={"sensor_path": sensor_path, "limit": 1}
            )
            
            if response.status_code == 200:
                current_data = response.json()
                
                if not current_data:
                    return f"❌ Sensor '{sensor_path}' nicht gefunden oder keine Daten verfügbar."
                
                # Historische Daten für Statistiken (letzten 1000 Einträge)
                history_response = await client.get(
                    f"{API_BASE_URL}/sensors/", 
                    params={"sensor_path": sensor_path, "limit": 1000}
                )
                
                output = f"📊 Sensor-Zusammenfassung: {sensor_path}\n\n"
                
                # Aktuelle Werte
                latest = current_data[0]
                output += "🔴 Aktuelle Werte:\n"
                berlin_time = format_berlin_time(latest['ts_collected'])
                output += f"⏰ Letztes Update: {berlin_time}\n"
                
                decoded = latest.get('decoded_data', {})
                if decoded:
                    measurements = []
                    
                    if 'temperature' in decoded:
                        temp = decoded['temperature'][0] if isinstance(decoded['temperature'], list) else decoded['temperature']
                        measurements.append(f"🌡️  {temp:.1f}°C")
                    
                    if 'humidity' in decoded:
                        humidity = decoded['humidity'][0] if isinstance(decoded['humidity'], list) else decoded['humidity']
                        measurements.append(f"💧 {humidity:.1f}%")
                    
                    if 'co2' in decoded:
                        co2 = decoded['co2'][0] if isinstance(decoded['co2'], list) else decoded['co2']
                        measurements.append(f"🌬️  {co2:.0f} ppm")
                    
                    output += " | ".join(measurements) + "\n\n"
                
                # Einfache Statistiken aus historischen Daten
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    if len(history_data) > 1:
                        # Zeitraum der Daten bestimmen
                        jüngste_messung = format_berlin_time(history_data[0]['ts_collected'])
                        älteste_messung = format_berlin_time(history_data[-1]['ts_collected'])
                        
                        output += f"📈 Verlaufs-Statistiken (letzte {len(history_data)} Datenpunkte):\n"
                        output += f"📅 Zeitraum: {älteste_messung} bis {jüngste_messung}\n\n"
                        
                        # Temperatur-Statistiken berechnen
                        temps = []
                        co2_values = []
                        
                        for item in history_data:
                            item_decoded = item.get('decoded_data', {})
                            if 'temperature' in item_decoded:
                                temp = item_decoded['temperature']
                                temp_val = temp[0] if isinstance(temp, list) else temp
                                temps.append(temp_val)
                            
                            if 'co2' in item_decoded:
                                co2 = item_decoded['co2']
                                co2_val = co2[0] if isinstance(co2, list) else co2
                                co2_values.append(co2_val)
                        
                        if temps:
                            output += f"🌡️  Temperatur: Min {min(temps):.1f}°C | Max {max(temps):.1f}°C | Ø {sum(temps)/len(temps):.1f}°C\n"
                        
                        if co2_values:
                            output += f"🌬️  CO2: Min {min(co2_values):.0f} | Max {max(co2_values):.0f} | Ø {sum(co2_values)/len(co2_values):.0f} ppm\n"
                
                return output
            
            elif response.status_code == 500:
                return "❌ Backend-Server-Fehler bei Sensor-Zusammenfassung."
            else:
                return f"❌ API-Fehler bei Sensor-Zusammenfassung: HTTP {response.status_code}"
                
    except httpx.ConnectError:
        return "❌ Verbindung zum Backend fehlgeschlagen. Ist das air-Q Backend gestartet?"
    except httpx.TimeoutException:
        return "❌ Timeout bei Sensor-Zusammenfassung."
    except Exception as e:
        return f"❌ Fehler bei Sensor-Zusammenfassung: {str(e)}"

@mcp.tool()
async def start_backend() -> str:
    """
    Hilfsfunktion: Gibt Anweisungen zum Starten des air-Q Backends.
    
    Returns:
        Anweisungen zum Backend-Start
    """
    return """🚀 air-Q Backend starten:

📋 Anweisungen:
1. Öffne ein Terminal im airq-Projektordner
2. Führe aus: docker-compose up -d
3. Warte bis alle Services gestartet sind
4. Teste mit: curl http://localhost:8000/sensors/health

🔗 Nach dem Start verfügbar:
• Backend API: http://localhost:8000
• API Docs: http://localhost:8000/docs  
• Grafana: http://localhost:3000
• Prometheus: http://localhost:9090

⚙️ Konfiguration prüfen:
Stelle sicher, dass die .env Datei korrekt konfiguriert ist:
• AIRQ_HOST=<deine-air-q-ip>
• AIRQ_PASSWORD=<dein-password>
• AIRQ_SENSORS=<komma-getrennte-sensor-pfade>

💡 Tipp: Nach dem Start dauert es ein paar Sekunden bis Daten gesammelt werden."""
