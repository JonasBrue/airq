"""
PDF Report Generator für air-Q Sensordaten.

Dieses Modul erstellt umfassende PDF-Berichte mit Diagrammen und Statistiken
für die Luftqualitätsmesswerte der air-Q Sensoren.
"""

import io
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, NamedTuple, Union
from dataclasses import dataclass
import tempfile

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SensorData

# Logger konfigurieren
logger = logging.getLogger(__name__)

def format_berlin_time(utc_datetime: Union[datetime, str]) -> str:
    """
    Konvertiert UTC-Zeit zu Berliner Zeit (MEZ/MESZ).
    
    Args:
        utc_datetime: UTC-Zeitstempel als datetime object oder String
    
    Returns:
        Formatierter Berliner Zeit-String mit Zeitzone (ohne Jahr)
    """
    try:
        if isinstance(utc_datetime, str):
            timestamp_str = utc_datetime.strip()
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1]
            utc_dt = datetime.fromisoformat(timestamp_str)
        else:
            utc_dt = utc_datetime
        
        # Berliner Zeit = UTC + 1 oder UTC + 2 (je nach Jahreszeit)
        month = utc_dt.month
        
        if 4 <= month <= 9:  # April bis September = Sommerzeit (MESZ)
            berlin_dt = utc_dt + timedelta(hours=2)
        else:  # Oktober bis März = Winterzeit (MEZ)
            berlin_dt = utc_dt + timedelta(hours=1)
        
        return f"{berlin_dt.strftime('%d.%m %H:%M')}"
    
    except Exception as e:
        # Fallback: Original-Zeitstempel
        return str(utc_timestamp)

# Layout-Konstanten
class LayoutConstants:
    """Zentrale Layout-Konstanten für PDF-Generierung."""
    
    # Logo-Dimensionen
    LOGO_WIDTH = 80
    LOGO_HEIGHT = 30
    LOGO_SPACING = 350
    
    # Tabellen-Konstanten
    TABLE_HEADER_FONT_SIZE = 10
    TABLE_CELL_FONT_SIZE = 8
    TABLE_SMALL_FONT_SIZE = 7
    TABLE_PADDING = 8
    
    # Spaltenbreiten
    TIMESTAMP_COL_WIDTH = 60
    SENSOR_PATH_COL_WIDTH = 60
    METRIC_COL_WIDTH = 80
    VALUE_COL_WIDTH = 70
    DESCRIPTION_COL_WIDTH = 150
    
    # Metriken-Tabelle Spaltenbreiten
    METRIC_NAME_WIDTH = 65
    METRIC_VALUE_WIDTH = 60
    METRIC_STAT_WIDTH = 50
    METRIC_DESC_WIDTH = 140
    
    # Abstand-Konstanten
    STANDARD_SPACER = 20
    LARGE_SPACER = 40
    SMALL_SPACER = 10
    
    # Datenbank-Konstanten
    DEFAULT_DAYS_BACK = 30
    TABLE_SPLIT_THRESHOLD = 9
    MINUTES_TO_DISPLAY = 15
    
    # Chart-Konstanten
    CHART_WIDTH = 12
    CHART_HEIGHT = 6
    CHART_DPI = 300
    CHART_HOURS_WINDOW = 24  # Anzahl Stunden für Detailcharts


class ChartGenerator:
    """Generator für Diagramme der Sensor-Daten."""
    
    def __init__(self):
        # Deutsche Lokalisierung für Matplotlib
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['font.size'] = 10
        plt.rcParams['figure.facecolor'] = 'white'
        plt.rcParams['axes.facecolor'] = 'white'
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.alpha'] = 0.3
        plt.rcParams['axes.spines.top'] = False
        plt.rcParams['axes.spines.right'] = False
        
        # Farben für verschiedene Sensoren
        self.sensor_colors = [
            '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', 
            '#1B9E77', '#D95F02', '#7570B3', '#E7298A'
        ]
    
    def create_time_series_chart(self, data_by_sensor: Dict[str, List], 
                                metric_key: str, 
                                time_range: Tuple[datetime, datetime],
                                chart_type: str = "overview") -> str:
        """
        Erstellt ein Zeitreihen-Diagramm für eine Metrik.
        
        Args:
            data_by_sensor: Dictionary mit Sensor-Pfad als Key und Liste der SensorData als Werte
            metric_key: Key der Metrik (z.B. 'temperature', 'co2')
            time_range: Tuple mit Start- und End-Zeitpunkt
            chart_type: 'overview' für kompletten Zeitraum oder 'detail' für letzten Tag
        
        Returns:
            Pfad zur gespeicherten Chart-Datei
        """
        metric_def = MetricRegistry.get_definition(metric_key)
        
        # Figure erstellen
        fig, ax = plt.subplots(figsize=(LayoutConstants.CHART_WIDTH, LayoutConstants.CHART_HEIGHT))
        
        has_data = False
        
        for i, (sensor_path, sensor_data) in enumerate(data_by_sensor.items()):
            if not sensor_data:
                continue
                
            # Zeitpunkte und Werte extrahieren
            timestamps = []
            values = []
            
            for record in reversed(sensor_data):  # Chronologisch sortieren
                value = self._extract_sensor_value(record.decoded_data, metric_key)
                if value is not None:
                    # Filterung nach chart_type
                    if chart_type == "detail":
                        # Nur letzten Tag anzeigen
                        if record.ts_collected >= time_range[1] - timedelta(hours=LayoutConstants.CHART_HOURS_WINDOW):
                            timestamps.append(record.ts_collected)
                            values.append(value)
                    else:
                        timestamps.append(record.ts_collected)
                        values.append(value)
            
            if timestamps and values:
                has_data = True
                color = self.sensor_colors[i % len(self.sensor_colors)]
                
                ax.plot(timestamps, values, 
                       label=sensor_path, 
                       color=color, 
                       linewidth=2,
                       alpha=0.8)
        
        if not has_data:
            ax.text(0.5, 0.5, 'Keine Daten verfügbar', 
                   transform=ax.transAxes, ha='center', va='center', 
                   fontsize=14, alpha=0.5)
        
        # Achsen formatieren
        ax.set_title(f'{metric_def.title} ({metric_def.description}) - {"Letzte 24 Stunden" if chart_type == "detail" else "Übersicht"}', 
                    fontsize=14, fontweight='bold', pad=20)
        ax.set_ylabel(f'{metric_def.title} ({metric_def.unit})')
        
        # Zeitachse formatieren
        if chart_type == "detail":
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
            ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(timestamps) // 10)))
        
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
        
        # Legend
        if len(data_by_sensor) > 1 and has_data:
            ax.legend(loc='upper right', framealpha=0.9)
        
        # Layout optimieren
        plt.tight_layout()
        
        # Als temporäre Datei speichern
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(temp_file.name, dpi=LayoutConstants.CHART_DPI, 
                   bbox_inches='tight', facecolor='white')
        plt.close(fig)
        
        return temp_file.name
    
    def create_multi_metric_overview(self, data_by_sensor: Dict[str, List],
                                   metrics: List[str],
                                   time_range: Tuple[datetime, datetime]) -> str:
        """
        Erstellt ein Multi-Panel-Diagramm mit mehreren Metriken.
        
        Args:
            data_by_sensor: Dictionary mit Sensor-Daten
            metrics: Liste der anzuzeigenden Metriken
            time_range: Zeitbereich
        
        Returns:
            Pfad zur gespeicherten Chart-Datei
        """
        if not metrics:
            return None
        
        # Flexibles Grid basierend auf Anzahl der Metriken
        num_metrics = len(metrics)
        if num_metrics <= 4:
            rows, cols = 2, 2
        elif num_metrics <= 6:
            rows, cols = 2, 3
        elif num_metrics <= 9:
            rows, cols = 3, 3
        elif num_metrics <= 12:
            rows, cols = 3, 4
        else:
            rows, cols = 4, 4
            metrics = metrics[:16]  # Max 16 Metriken
        
        # Größe anpassen basierend auf Grid
        fig_width = LayoutConstants.CHART_WIDTH * (cols / 2)
        fig_height = LayoutConstants.CHART_HEIGHT * (rows / 2)
        
        fig, axes = plt.subplots(rows, cols, figsize=(fig_width, fig_height))
        
        # Für ein einzelnes Subplot axes zu einer Liste machen
        if rows == 1 and cols == 1:
            axes = [axes]
        elif rows == 1 or cols == 1:
            axes = axes.flatten()
        else:
            axes = axes.flatten()
        
        for i, metric_key in enumerate(metrics):
            ax = axes[i]
            metric_def = MetricRegistry.get_definition(metric_key)
            
            has_data = False
            
            for j, (sensor_path, sensor_data) in enumerate(data_by_sensor.items()):
                if not sensor_data:
                    continue
                    
                # Zeitpunkte und Werte extrahieren (letzte 24 Stunden)
                timestamps = []
                values = []
                
                cutoff_time = time_range[1] - timedelta(hours=LayoutConstants.CHART_HOURS_WINDOW)
                
                for record in reversed(sensor_data):
                    if record.ts_collected >= cutoff_time:
                        value = self._extract_sensor_value(record.decoded_data, metric_key)
                        if value is not None:
                            timestamps.append(record.ts_collected)
                            values.append(value)
                
                if timestamps and values:
                    has_data = True
                    color = self.sensor_colors[j % len(self.sensor_colors)]
                    
                    ax.plot(timestamps, values, 
                           label=sensor_path if len(data_by_sensor) > 1 else None,
                           color=color, 
                           linewidth=1.5,
                           alpha=0.8)
            
            if not has_data:
                ax.text(0.5, 0.5, 'Keine Daten', 
                       transform=ax.transAxes, ha='center', va='center', 
                       fontsize=10, alpha=0.5)
            
            # Achsen formatieren
            ax.set_title(metric_def.title, fontsize=12, fontweight='bold')
            ax.set_ylabel(f'({metric_def.unit})')
            
            # Zeitachse
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=9)
            
            # Grid
            ax.grid(True, alpha=0.3)
        
        # Eventuell leere Subplots verstecken
        total_subplots = rows * cols
        for i in range(len(metrics), total_subplots):
            if i < len(axes):
                axes[i].set_visible(False)
        
        # Gemeinsame Legende wenn mehrere Sensoren
        if len(data_by_sensor) > 1:
            handles, labels = axes[0].get_legend_handles_labels()
            if handles:
                fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.02), 
                          ncol=min(4, len(labels)), framealpha=0.9)
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.15)
        
        # Als temporäre Datei speichern
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        plt.savefig(temp_file.name, dpi=LayoutConstants.CHART_DPI, 
                   bbox_inches='tight', facecolor='white')
        plt.close(fig)
        
        return temp_file.name
    
    def _extract_sensor_value(self, decoded_data: Dict[str, Any], key: str) -> Optional[float]:
        """Extrahiert einen Sensorwert aus decoded_data."""
        if key not in decoded_data:
            return None
            
        value = decoded_data[key]
        
        # air-Q gibt oft [Wert, Fehler] zurück
        if isinstance(value, list) and len(value) > 0:
            return float(value[0]) if value[0] is not None else None
        elif isinstance(value, (int, float)):
            return float(value)
        else:
            return None


# Farbschema
COLORS = {
    'primary': HexColor('#2E86AB'),
    'secondary': HexColor('#A23B72'),
    'success': HexColor('#F18F01'),
    'warning': HexColor('#C73E1D'),
    'dark': HexColor('#1B2631'),
    'light': HexColor('#F8F9FA')
}

# Tabellen-Styles
TABLE_HEADER_STYLE = [
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('BOTTOMPADDING', (0, 0), (-1, 0), LayoutConstants.TABLE_PADDING),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black),
]

@dataclass
class MetricDefinition:
    """Definition einer Metrik mit allen relevanten Eigenschaften."""
    title: str
    unit: str
    description: str
    decimal_places: int = 1
    
    def format_value(self, value: float) -> str:
        """Formatiert einen Wert gemäß der Metrik-Definition."""
        if self.decimal_places == 0:
            return f'{value:.0f}{" " + self.unit if self.unit else ""}'
        else:
            return f'{value:.{self.decimal_places}f}{" " + self.unit if self.unit else ""}'


class MetricRegistry:
    """Zentrale Registry für alle Metrik-Definitionen."""
    
    METRICS = {
        'temperature': MetricDefinition('Temperatur', '°C', 'Raumtemperatur in °C'),
        'humidity': MetricDefinition('Feuchtigkeit', '%', 'Relative Feuchtigkeit in %'),
        'co2': MetricDefinition('CO2', 'ppm', 'Kohlendioxid-Konzentration in ppm', 0),
        'pressure': MetricDefinition('Luftdruck', 'hPa', 'Absoluter Druck in hPa'),
        'health': MetricDefinition('Gesund.-Index', '', 'Bewertung 0-1000', 0),
        'dewpt': MetricDefinition('Taupunkt', '°C', 'Kondensationstemperatur in °C'),
        'humidity_abs': MetricDefinition('Abs. Feuchtig.', 'g/m³', 'Wasserdampf in g/m³'),
        'co': MetricDefinition('CO', 'mg/m³', 'Kohlenmonoxid-Konzentration in mg/m³', 2),
        'pm1': MetricDefinition('PM1 FS', 'µg/m³', 'Feinstaub Partikel <1µm in µg/m³'),
        'pm2_5': MetricDefinition('PM2.5 FS', 'µg/m³', 'Feinstaub Partikel <2.5µm in µg/m³'),
        'pm10': MetricDefinition('PM10 FS', 'µg/m³', 'Feinstaub Partikel <10µm in µg/m³'),
        'TypPS': MetricDefinition('Partikelgröße', 'µm', 'Durchschnittsgröße in µm'),
        'no2': MetricDefinition('NO2', 'ppm', 'Stickstoffdioxid-Konz. in ppm', 0),
        'h2s': MetricDefinition('H2S', 'µg/m³', 'Schwefelwasserstoff-Konz. in µg/m³'),
        'o3': MetricDefinition('O3', 'µg/m³', 'Ozon-Konzentration in µg/m³'),
        'tvoc': MetricDefinition('TVOC', 'ppb', 'Flüchtige org. Verbindungen in ppb', 0),
        'oxygen': MetricDefinition('Sauerstoff', 'Vol.-%', 'O2-Konzentration in Vol.-%'),
        'sound': MetricDefinition('Geräusche', 'dB(A)', 'Lärm in dB(A)'),
    }
    
    # Alle verfügbaren Metriken in logischer Reihenfolge
    ALL_METRICS = [
        'temperature', 'humidity', 'co2', 'pressure', 'health',
        'pm1', 'pm2_5', 'pm10', 'TypPS', 'no2', 'h2s', 'o3', 'tvoc',
        'dewpt', 'humidity_abs', 'co', 'oxygen', 'sound'
    ]
    
    @classmethod
    def get_definition(cls, key: str) -> MetricDefinition:
        """Gibt die Definition einer Metrik zurück."""
        return cls.METRICS.get(key, MetricDefinition(
            title=key,
            unit='',
            description=f'{key} (Einheit unbekannt)'
        ))
    
    @classmethod
    def get_available_metrics(cls, data: List[SensorData]) -> List[str]:
        """Ermittelt verfügbare Metriken aus den Daten in der definierten Reihenfolge."""
        available_in_data = set()
        for record in data:
            available_in_data.update(record.decoded_data.keys())
        
        # Rückgabe in der definierten Reihenfolge von ALL_METRICS
        return [metric for metric in cls.ALL_METRICS if metric in available_in_data]


class SVGFlowable(Flowable):
    """Flowable für SVG-Grafiken in ReportLab."""
    
    def __init__(self, svg_path: str, width: float, height: float):
        super().__init__()
        self.svg_path = svg_path
        self.width = width
        self.height = height
        self.svg_drawing = None
        self._load_svg()
    
    def _load_svg(self) -> None:
        """Lädt die SVG-Datei und konvertiert sie zu einer ReportLab-Grafik."""
        try:
            if not os.path.exists(self.svg_path):
                logger.warning(f"SVG-Datei nicht gefunden: {self.svg_path}")
                return
                
            from svglib.svglib import svg2rlg
            self.svg_drawing = svg2rlg(self.svg_path)
            
            if self.svg_drawing and self.svg_drawing.width > 0 and self.svg_drawing.height > 0:
                # Proportional skalieren
                scale_x = self.width / self.svg_drawing.width
                scale_y = self.height / self.svg_drawing.height
                scale = min(scale_x, scale_y)
                
                self.svg_drawing.width *= scale
                self.svg_drawing.height *= scale
                self.svg_drawing.scale(scale, scale)
            else:
                logger.warning(f"Ungültige SVG-Dimensionen: {self.svg_path}")
                self.svg_drawing = None
                
        except Exception as e:
            logger.warning(f"Fehler beim Laden der SVG-Datei {self.svg_path}: {e}")
            self.svg_drawing = None
    
    def draw(self) -> None:
        """Zeichnet die SVG-Grafik."""
        if self.svg_drawing:
            try:
                from reportlab.graphics import renderPDF
                renderPDF.draw(self.svg_drawing, self.canv, 0, 0)
            except Exception as e:
                logger.warning(f"Fehler beim Zeichnen der SVG-Grafik: {e}")
    
    def wrap(self, available_width: float, available_height: float) -> Tuple[float, float]:
        """Gibt die Größe der Grafik zurück."""
        if self.svg_drawing:
            return self.svg_drawing.width, self.svg_drawing.height
        return self.width, self.height 


class AirQualityPDFGenerator:
    """Generator für PDF-Berichte von air-Q Sensordaten."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.styles = getSampleStyleSheet()
        self._setup_styles()
        self.logo_paths = self._get_logo_paths()
        self.chart_generator = ChartGenerator()
        self.temp_chart_files = []  # Zum späteren Cleanup
    
    def _setup_styles(self) -> None:
        """Erstellt benutzerdefinierte Styles für das PDF."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=20,
            spaceAfter=LayoutConstants.STANDARD_SPACER,
            alignment=TA_CENTER,
            textColor=COLORS['dark']
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=LayoutConstants.STANDARD_SPACER,
            textColor=COLORS['primary']
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=LayoutConstants.SMALL_SPACER + 5,
            textColor=COLORS['secondary']
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatValue',
            parent=self.styles['Normal'],
            fontSize=24,
            alignment=TA_CENTER,
            textColor=COLORS['primary'],
            spaceAfter=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            textColor=COLORS['dark']
        ))
        
        self.styles.add(ParagraphStyle(
            name='CenteredTimeRange',
            parent=self.styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=LayoutConstants.STANDARD_SPACER
        ))
    
    def _get_logo_paths(self) -> Dict[str, str]:
        """Ermittelt die Pfade zu den Logo-Dateien."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return {
            'dcaiti': os.path.join(current_dir, 'img', 'dcaiti.svg'),
            'fraunhofer': os.path.join(current_dir, 'img', 'fraunhofer.svg')
        }
    
    def _create_logo_table(self) -> Optional[Table]:
        """Erstellt eine Tabelle mit beiden Logos (links und rechts)."""
        try:
            left_logo = None
            right_logo = None
            
            if os.path.exists(self.logo_paths['fraunhofer']):
                left_logo = SVGFlowable(
                    self.logo_paths['fraunhofer'], 
                    LayoutConstants.LOGO_WIDTH, 
                    LayoutConstants.LOGO_HEIGHT
                )
            
            if os.path.exists(self.logo_paths['dcaiti']):
                right_logo = SVGFlowable(
                    self.logo_paths['dcaiti'], 
                    LayoutConstants.LOGO_WIDTH, 
                    LayoutConstants.LOGO_HEIGHT
                )
            
            table_data = [[
                left_logo or "",
                "",  # Spacer
                right_logo or ""
            ]]
            
            logo_table = Table(table_data, colWidths=[
                LayoutConstants.LOGO_WIDTH, 
                LayoutConstants.LOGO_SPACING, 
                LayoutConstants.LOGO_WIDTH
            ])
            
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            return logo_table
            
        except Exception as e:
            logger.warning(f"Fehler beim Erstellen der Logo-Tabelle: {e}")
            return None
    
    async def generate_report(self, output_buffer: io.BytesIO) -> None:
        """Hauptmethode zur Generierung des PDF-Berichts."""
        logger.info("Starte PDF-Berichtsgenerierung")
        
        data = await self._load_data()
        
        if not data:
            logger.warning("Keine Daten für Bericht vorhanden")
            self._create_empty_report(output_buffer)
            return
        
        doc = SimpleDocTemplate(output_buffer, pagesize=A4)
        story = []
        
        # Übersichtsseite
        story.extend(self._create_overview_page(data))
        
        # Detailseiten für jeden Sensor
        for sensor_path in data['sensors']:
            story.append(PageBreak())
            story.extend(self._create_sensor_detail_page(data, sensor_path))
        
        doc.build(story)
        logger.info("PDF-Bericht erfolgreich generiert")
        
        # Cleanup temporärer Chart-Dateien
        self._cleanup_temp_files()
    
    def _create_empty_report(self, output_buffer: io.BytesIO) -> None:
        """Erstellt einen leeren Bericht wenn keine Daten vorhanden sind."""
        doc = SimpleDocTemplate(output_buffer, pagesize=A4)
        story = [
            Paragraph("air-Q Luftqualitätsbericht", self.styles['CustomTitle']),
            Spacer(1, LayoutConstants.STANDARD_SPACER),
            Paragraph("Keine Daten verfügbar", self.styles['Normal'])
        ]
        doc.build(story)
    
    async def _load_data(self) -> Optional[Dict[str, Any]]:
        """Lädt alle notwendigen Daten aus der Datenbank."""
        try:
            # Verfügbare Sensoren ermitteln
            sensors_stmt = select(SensorData.sensor_path).distinct()
            sensors_result = await self.session.execute(sensors_stmt)
            sensors = [row[0] for row in sensors_result.fetchall()]
            
            if not sensors:
                return None
            
            # Zeitraum ermitteln
            time_range_stmt = select(
                func.min(SensorData.ts_collected),
                func.max(SensorData.ts_collected)
            )
            time_result = await self.session.execute(time_range_stmt)
            earliest, latest = time_result.fetchone()
            
            if not earliest or not latest:
                return None
            
            # Daten der letzten 30 Tage laden
            since = max(earliest, latest - timedelta(days=LayoutConstants.DEFAULT_DAYS_BACK))
            
            data_stmt = select(SensorData).where(
                SensorData.ts_collected >= since
            ).order_by(SensorData.ts_collected.desc())
            
            data_result = await self.session.execute(data_stmt)
            all_data = list(data_result.scalars())
            
            return {
                'sensors': sensors,
                'earliest': earliest,
                'latest': latest,
                'data': all_data,
                'time_range': (since, latest)
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Daten: {e}")
            return None
    
    def _create_overview_page(self, data: Dict[str, Any]) -> List:
        """Erstellt die Übersichtsseite."""
        story = []
        
        # Logos
        logo_table = self._create_logo_table()
        if logo_table:
            story.append(logo_table)
            story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Titel mit Enddatum
        time_range = data['time_range']        
        story.append(Paragraph(f"air-Q Luftqualitätsbericht {time_range[1].day:02d}.{time_range[1].month:02d}.{time_range[1].year}", self.styles['CustomTitle']))
        
        # Zeitraum (in Berliner Zeit) - zentriert unter dem Titel
        story.append(Paragraph(
            f"{format_berlin_time(time_range[0])} - "
            f"{format_berlin_time(time_range[1])}",
            self.styles['CenteredTimeRange']
        ))
        
        # Sensor-Übersicht
        story.append(Paragraph("Sensor-Übersicht", self.styles['CustomHeading1']))
        story.extend(self._create_sensor_overview_table(data))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Gesamtstatistiken
        story.append(Paragraph("Gesamtstatistiken", self.styles['CustomHeading1']))
        story.extend(self._create_comprehensive_statistics(data))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Charts-Übersicht hinzufügen
        story.extend(self._create_overview_charts(data))
        
        return story
    
    def _create_sensor_detail_page(self, data: Dict[str, Any], sensor_path: str) -> List:
        """Erstellt eine Detailseite für einen Sensor."""
        story = []
        
        sensor_data = [d for d in data['data'] if d.sensor_path == sensor_path]
        
        if not sensor_data:
            story.append(Paragraph(f"Keine Daten für Sensor {sensor_path}", self.styles['Normal']))
            return story
        
        # Logos
        logo_table = self._create_logo_table()
        if logo_table:
            story.append(logo_table)
            story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Titel mit Jahr und Monat
        time_range = data['time_range']      
        
        story.append(Paragraph(f"Sensor {sensor_path} - Detailanalyse {time_range[1].day:02d}.{time_range[1].month:02d}.{time_range[1].year}", self.styles['CustomTitle']))
        
        # Berichtszeitraum (in Berliner Zeit) - zentriert unter dem Titel
        story.append(Paragraph(
            f"Zeitraum: {format_berlin_time(time_range[0])} - {format_berlin_time(time_range[1])}",
            self.styles['CenteredTimeRange']
        ))
        
        # Statistiken
        story.extend(self._create_sensor_statistics(sensor_data))
        story.append(PageBreak())

        # Minutenweise aggregierte Messwerte der letzten Minuten
        story.append(Paragraph(f"Aktuelle Messwerte (letzte {LayoutConstants.MINUTES_TO_DISPLAY} Minuten)", self.styles['CustomHeading2']))
        story.extend(self._create_sensor_values_table(sensor_data))
        story.append(PageBreak())

        # Charts für diesen Sensor hinzufügen
        story.extend(self._create_sensor_charts(data, sensor_path))

        return story
    
    def _create_table_with_style(self, table_data: List[List], col_widths: List[int], 
                                font_size: int = None) -> Table:
        """Erstellt eine Tabelle mit dem Standard-Style."""
        if not table_data:
            return None
        
        table = Table(table_data, colWidths=col_widths)
        
        style = list(TABLE_HEADER_STYLE)
        if font_size:
            style.extend([
                ('FONTSIZE', (0, 0), (-1, 0), font_size),
                ('FONTSIZE', (0, 1), (-1, -1), max(font_size - 2, 6)),
            ])
        else:
            style.extend([
                ('FONTSIZE', (0, 0), (-1, 0), LayoutConstants.TABLE_HEADER_FONT_SIZE),
                ('FONTSIZE', (0, 1), (-1, -1), LayoutConstants.TABLE_CELL_FONT_SIZE),
            ])
        
        table.setStyle(TableStyle(style))
        return table
    
    def _extract_sensor_value(self, decoded_data: Dict[str, Any], key: str) -> Optional[float]:
        """Extrahiert einen Sensorwert aus decoded_data."""
        if key not in decoded_data:
            return None
            
        value = decoded_data[key]
        
        # air-Q gibt oft [Wert, Fehler] zurück
        if isinstance(value, list) and len(value) > 0:
            return float(value[0]) if value[0] is not None else None
        elif isinstance(value, (int, float)):
            return float(value)
        else:
            return None
    
    def _format_sensor_value(self, value: Optional[float], metric_key: str) -> str:
        """Formatiert einen Sensorwert für die Anzeige."""
        if value is None:
            return 'N/A'
        
        metric_def = MetricRegistry.get_definition(metric_key)
        return metric_def.format_value(value)
    
    def _create_comprehensive_statistics(self, data: Dict[str, Any]) -> List:
        """Erstellt umfassende Statistiken für alle verfügbaren Metriken."""
        story = []
        
        all_data = data['data']
        if not all_data:
            story.append(Paragraph("Keine Daten verfügbar", self.styles['Normal']))
            return story
        
        available_metrics = MetricRegistry.get_available_metrics(all_data)
        
        if available_metrics:
            story.extend(self._create_metrics_table(all_data, available_metrics))
        
        return story
    
    def _create_metrics_table(self, all_data: List, metrics: List[str]) -> List:
        """Erstellt eine Tabelle für bestimmte Metriken."""
        if not metrics:
            return []
        
        table_data = [['Metrik', 'Durchschnitt', 'Minimum', 'Maximum', 'Beschreibung']]
        
        for metric in metrics:
            metric_def = MetricRegistry.get_definition(metric)
            
            # Werte extrahieren
            values = []
            for record in all_data:
                value = self._extract_sensor_value(record.decoded_data, metric)
                if value is not None:
                    values.append(value)
            
            if values:
                avg_val = np.mean(values)
                min_val = np.min(values)
                max_val = np.max(values)
                
                table_data.append([
                    metric_def.title,
                    metric_def.format_value(avg_val),
                    metric_def.format_value(min_val),
                    metric_def.format_value(max_val),
                    metric_def.description
                ])
        
        if len(table_data) > 1:
            table = self._create_table_with_style(
                table_data, 
                [LayoutConstants.METRIC_COL_WIDTH, LayoutConstants.VALUE_COL_WIDTH, 
                 LayoutConstants.VALUE_COL_WIDTH, LayoutConstants.VALUE_COL_WIDTH, 
                 LayoutConstants.DESCRIPTION_COL_WIDTH]
            )
            return [table]
        
        return []
    
    def _create_sensor_overview_table(self, data: Dict[str, Any]) -> List:
        """Erstellt eine Sensor-Übersichtstabelle."""
        table_data = [['Sensor', 'Letzte Messung', 'Temperatur', 'Luftfeuchtigkeit', 'CO2', 'Luftdruck', 'Gesund.-Index']]
        
        for sensor_path in data['sensors']:
            sensor_data = [d for d in data['data'] if d.sensor_path == sensor_path]
            if not sensor_data:
                continue
            
            latest = sensor_data[0]
            decoded = latest.decoded_data
            
            table_data.append([
                sensor_path,
                format_berlin_time(latest.ts_collected),
                self._format_sensor_value(self._extract_sensor_value(decoded, 'temperature'), 'temperature'),
                self._format_sensor_value(self._extract_sensor_value(decoded, 'humidity'), 'humidity'),
                self._format_sensor_value(self._extract_sensor_value(decoded, 'co2'), 'co2'),
                self._format_sensor_value(self._extract_sensor_value(decoded, 'pressure'), 'pressure'),
                self._format_sensor_value(self._extract_sensor_value(decoded, 'health'), 'health')
            ])
        
        if len(table_data) > 1:
            table = self._create_table_with_style(
                table_data, 
                [LayoutConstants.TIMESTAMP_COL_WIDTH, 80, 
                 LayoutConstants.TIMESTAMP_COL_WIDTH, LayoutConstants.VALUE_COL_WIDTH, 
                 LayoutConstants.TIMESTAMP_COL_WIDTH, LayoutConstants.TIMESTAMP_COL_WIDTH, 
                 LayoutConstants.VALUE_COL_WIDTH],
                9
            )
            return [table]
        
        return []
    
    def _create_sensor_statistics(self, sensor_data: List) -> List:
        """Erstellt Statistiken für einen einzelnen Sensor."""
        if not sensor_data:
            return []
        
        story = []
        available_metrics = MetricRegistry.get_available_metrics(sensor_data)
        
        if available_metrics:
            story.append(Paragraph("Sensor-Metriken", self.styles['CustomHeading2']))
            story.extend(self._create_sensor_metrics_table(sensor_data, available_metrics))
            story.append(Spacer(1, LayoutConstants.SMALL_SPACER + 5))
        
        return story
    
    def _create_sensor_metrics_table(self, sensor_data: List, metrics: List[str]) -> List:
        """Erstellt eine Tabelle für bestimmte Metriken eines Sensors."""
        if not metrics:
            return []
        
        table_data = [['Metrik', 'Durchschnitt', 'SD', 'Minimum', 'Maximum', 'Beschreibung']]
        
        for metric in metrics:
            metric_def = MetricRegistry.get_definition(metric)
            
            # Werte extrahieren
            values = []
            for record in sensor_data:
                value = self._extract_sensor_value(record.decoded_data, metric)
                if value is not None:
                    values.append(value)
            
            if values:
                avg_val = np.mean(values)
                std_val = np.std(values)
                min_val = np.min(values)
                max_val = np.max(values)
                
                table_data.append([
                    metric_def.title,
                    metric_def.format_value(avg_val),
                    metric_def.format_value(std_val),
                    metric_def.format_value(min_val),
                    metric_def.format_value(max_val),
                    metric_def.description
                ])
        
        if len(table_data) > 1:
            table = self._create_table_with_style(
                table_data, 
                [LayoutConstants.METRIC_NAME_WIDTH, LayoutConstants.METRIC_VALUE_WIDTH, 
                 LayoutConstants.METRIC_VALUE_WIDTH, LayoutConstants.METRIC_STAT_WIDTH, 
                 LayoutConstants.METRIC_STAT_WIDTH, LayoutConstants.METRIC_DESC_WIDTH],
                9
            )
            return [table]
        
        return []
    
    def _create_sensor_values_table(self, sensor_data: List) -> List:
        """Erstellt eine Tabelle mit minutenweise aggregierten Messwerten der letzten Minuten."""
        if not sensor_data:
            return []
        
        available_metrics = MetricRegistry.get_available_metrics(sensor_data)
        
        if not available_metrics:
            return []
        
        # Daten nach Minuten gruppieren und aggregieren
        minute_data = self._aggregate_data_by_minute(sensor_data, available_metrics)
        
        if not minute_data:
            return []
        
        # Tabelle-Header
        headers = ['Zeit'] + [MetricRegistry.get_definition(m).title for m in available_metrics]
        table_data = [headers]
        
        # Daten für jede Minute (chronologisch absteigend - neueste zuerst)
        for minute_timestamp, metric_averages in minute_data:
            row = [format_berlin_time(minute_timestamp)]
            
            for metric in available_metrics:
                avg_value = metric_averages.get(metric)
                row.append(self._format_sensor_value(avg_value, metric))
            
            table_data.append(row)
        
        if len(table_data) > 1:
            num_metrics = len(available_metrics)
            
            # Dynamische Spaltenbreiten
            if num_metrics <= 4:
                col_widths = [LayoutConstants.TIMESTAMP_COL_WIDTH] + [80] * num_metrics
            elif num_metrics <= 6:
                col_widths = [50] + [LayoutConstants.TIMESTAMP_COL_WIDTH] * num_metrics
            else:
                col_widths = [40] + [50] * num_metrics
            
            # Tabelle aufteilen wenn zu viele Spalten
            if num_metrics > LayoutConstants.TABLE_SPLIT_THRESHOLD:
                return self._create_split_table(table_data, headers, num_metrics)
            else:
                table = self._create_table_with_style(table_data, col_widths, 8)
                return [table]
        
        return []
    
    def _aggregate_data_by_minute(self, sensor_data: List, available_metrics: List[str]) -> List[Tuple[datetime, Dict[str, float]]]:
        """
        Aggregiert Sensor-Daten nach Minuten und berechnet Durchschnittswerte.
        
        Args:
            sensor_data: Liste der Sensor-Datensätze
            available_metrics: Liste der verfügbaren Metriken
            
        Returns:
            Liste von Tupeln (minute_timestamp, metric_averages) für die letzten konfigurierten Minuten,
            sortiert chronologisch absteigend (neueste zuerst)
        """
        from collections import defaultdict
        
        # Gruppierung nach Minuten
        minute_groups = defaultdict(lambda: defaultdict(list))
        
        for record in sensor_data:
            # Zeitstempel auf Minute runden (Sekunden auf 0 setzen)
            minute_timestamp = record.ts_collected.replace(second=0, microsecond=0)
            
            for metric in available_metrics:
                value = self._extract_sensor_value(record.decoded_data, metric)
                if value is not None:
                    minute_groups[minute_timestamp][metric].append(value)
        
        # Durchschnittswerte berechnen und sortieren
        aggregated_data = []
        for minute_timestamp, metrics_data in minute_groups.items():
            metric_averages = {}
            
            for metric in available_metrics:
                values = metrics_data.get(metric, [])
                if values:
                    metric_averages[metric] = sum(values) / len(values)
                else:
                    metric_averages[metric] = None
            
            aggregated_data.append((minute_timestamp, metric_averages))
        
        # Nach Zeitstempel absteigend sortieren (neueste zuerst)
        aggregated_data.sort(key=lambda x: x[0], reverse=True)
        
        # Nur die konfigurierten Anzahl Minuten zurückgeben
        return aggregated_data[:LayoutConstants.MINUTES_TO_DISPLAY]
    
    def _create_split_table(self, table_data: List[List], headers: List[str], num_metrics: int) -> List:
        """Erstellt geteilte Tabellen wenn zu viele Spalten vorhanden sind."""
        story = []
        
        # Erste Tabelle mit ersten 9 Metriken
        first_headers = headers[:LayoutConstants.TABLE_SPLIT_THRESHOLD + 1]  # Zeitstempel + 9 Metriken
        first_data = [first_headers]
        for row in table_data[1:]:
            first_data.append(row[:LayoutConstants.TABLE_SPLIT_THRESHOLD + 1])
        
        first_table = self._create_table_with_style(
            first_data, 
            [40] + [50] * LayoutConstants.TABLE_SPLIT_THRESHOLD,
            8
        )
        story.append(first_table)
        story.append(Spacer(1, LayoutConstants.SMALL_SPACER))
        
        # Zweite Tabelle mit restlichen Metriken
        if num_metrics > LayoutConstants.TABLE_SPLIT_THRESHOLD:
            second_headers = ['Zeit'] + headers[LayoutConstants.TABLE_SPLIT_THRESHOLD + 1:]
            second_data = [second_headers]
            for row in table_data[1:]:
                second_row = [row[0]] + row[LayoutConstants.TABLE_SPLIT_THRESHOLD + 1:]
                second_data.append(second_row)
            
            remaining_metrics = num_metrics - LayoutConstants.TABLE_SPLIT_THRESHOLD
            second_table = self._create_table_with_style(
                second_data, 
                [40] + [50] * remaining_metrics,
                8
            )
            story.append(second_table)
        
        return story 
    
    def _cleanup_temp_files(self) -> None:
        """Löscht temporäre Chart-Dateien."""
        for file_path in self.temp_chart_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Fehler beim Löschen der temporären Datei {file_path}: {e}")
        self.temp_chart_files.clear()
    
    def _organize_data_by_sensor(self, all_data: List) -> Dict[str, List]:
        """Organisiert die Daten nach Sensor-Pfad."""
        data_by_sensor = {}
        for record in all_data:
            sensor_path = record.sensor_path
            if sensor_path not in data_by_sensor:
                data_by_sensor[sensor_path] = []
            data_by_sensor[sensor_path].append(record)
        return data_by_sensor
    
    def _create_chart_image(self, chart_path: str, width: int = 480) -> Image:
        """Erstellt ein ReportLab Image-Objekt aus einem Chart-Pfad."""
        if not os.path.exists(chart_path):
            return None
        
        # Chart-Datei zur Cleanup-Liste hinzufügen
        if chart_path not in self.temp_chart_files:
            self.temp_chart_files.append(chart_path)
        
        # Bild proportional skalieren
        img = Image(chart_path)
        img.drawWidth = width
        img.drawHeight = width * 0.5  # 2:1 Verhältnis
        
        return img
    
    def _create_overview_charts(self, data: Dict[str, Any]) -> List:
        """Erstellt einzelne große Charts für alle Metriken - 2 pro Seite über 9 Seiten."""
        story = []
        all_data = data['data']
        time_range = data['time_range']
        
        if not all_data:
            return story
        
        # Daten nach Sensoren organisieren
        data_by_sensor = self._organize_data_by_sensor(all_data)
        available_metrics = MetricRegistry.get_available_metrics(all_data)
        
        if not available_metrics:
            return story
        
        # Überschrift nur einmal am Anfang
        story.append(Paragraph("Luftqualitäts-Trends", self.styles['CustomHeading1']))
        
        # Alle 18 Metriken einzeln, 2 pro Seite
        charts_on_current_page = 0
        
        for i, metric_key in enumerate(available_metrics):
            try:
                # Einzelnes großes Zeitreihen-Chart für diese Metrik
                chart_path = self.chart_generator.create_time_series_chart(
                    data_by_sensor, metric_key, time_range, chart_type="detail"
                )
                
                if chart_path:
                    chart_img = self._create_chart_image(chart_path, width=500)
                    if chart_img:
                        story.append(chart_img)
                        story.append(Spacer(1, LayoutConstants.SMALL_SPACER))
                        charts_on_current_page += 1
                        
                        # Nach 2 Charts eine neue Seite (außer bei den letzten)
                        if charts_on_current_page == 2 and i < len(available_metrics) - 1:
                            story.append(PageBreak())
                            charts_on_current_page = 0
                
            except Exception as e:
                logger.warning(f"Fehler beim Erstellen des Charts für {metric_key}: {e}")
        
        return story
    
    def _create_sensor_charts(self, data: Dict[str, Any], sensor_path: str) -> List:
        """Erstellt einzelne große Charts für alle Metriken eines Sensors - 2 pro Seite über 9 Seiten."""
        story = []
        all_data = data['data']
        time_range = data['time_range']
        
        # Daten für diesen Sensor filtern
        sensor_data = [d for d in all_data if d.sensor_path == sensor_path]
        
        if not sensor_data:
            return story
        
        data_by_sensor = {sensor_path: sensor_data}
        available_metrics = MetricRegistry.get_available_metrics(sensor_data)
        
        if not available_metrics:
            return story
        
        # Überschrift nur einmal am Anfang
        story.append(Paragraph("Zeitreihen-Diagramme", self.styles['CustomHeading2']))
        
        # Alle 18 Metriken einzeln, 2 pro Seite
        charts_on_current_page = 0
        
        for i, metric_key in enumerate(available_metrics):
            try:
                # Einzelnes großes Zeitreihen-Chart für diese Metrik
                chart_path = self.chart_generator.create_time_series_chart(
                    data_by_sensor, metric_key, time_range, chart_type="overview"
                )
                
                if chart_path:
                    chart_img = self._create_chart_image(chart_path, width=500)
                    if chart_img:
                        story.append(chart_img)
                        story.append(Spacer(1, LayoutConstants.SMALL_SPACER))
                        charts_on_current_page += 1
                        
                        # Nach 2 Charts eine neue Seite (außer bei den letzten)
                        if charts_on_current_page == 2 and i < len(available_metrics) - 1:
                            story.append(PageBreak())
                            charts_on_current_page = 0
                
            except Exception as e:
                logger.warning(f"Fehler beim Erstellen des Charts für {metric_key}: {e}")
        
        return story 