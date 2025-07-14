"""
PDF Report Generator für air-Q Sensordaten.

Dieses Modul erstellt umfassende PDF-Berichte mit Diagrammen und Statistiken
für die Luftqualitätsmesswerte der air-Q Sensoren.
"""

import io
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, NamedTuple
from dataclasses import dataclass

import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import SensorData

# Logger konfigurieren
logger = logging.getLogger(__name__)

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
    MAX_RECENT_VALUES = 15
    TABLE_SPLIT_THRESHOLD = 9


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
        'h2s': MetricDefinition('H2S', 'µg/m³', 'Schwefelwasserstoff-Konzentration in µg/m³'),
        'o3': MetricDefinition('O3', 'µg/m³', 'Ozon-Konzentration in µg/m³'),
        'tvoc': MetricDefinition('TVOC', 'ppb', 'Flüchtige org. Verbindungen in ppb', 0),
        'oxygen': MetricDefinition('Sauerstoff', 'Vol.-%', 'O2-Konzentration in Vol.-%'),
        'sound': MetricDefinition('Geräusche', 'dB(A)', 'Lärm in dB(A)'),
    }
    
    # Metrik-Gruppen
    MAIN_METRICS = [
        'temperature', 'humidity', 'co2', 'pressure', 'health',
        'pm1', 'pm2_5', 'pm10', 'TypPS', 'no2', 'h2s', 'o3', 'tvoc'
    ]
    
    OTHER_METRICS = ['dewpt', 'humidity_abs', 'co', 'oxygen', 'sound']
    
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
        """Ermittelt verfügbare Metriken aus den Daten."""
        all_metrics = set()
        for record in data:
            all_metrics.update(record.decoded_data.keys())
        
        # Filter relevante Metriken
        relevant_metrics = list(cls.METRICS.keys())
        return [m for m in relevant_metrics if m in all_metrics]


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
    
    def _setup_styles(self) -> None:
        """Erstellt benutzerdefinierte Styles für das PDF."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=20,
            spaceAfter=LayoutConstants.STANDARD_SPACER + 10,
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
        
        # Titel und Informationen
        story.append(Paragraph("air-Q Luftqualitätsbericht", self.styles['CustomTitle']))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Zeitraum
        time_range = data['time_range']
        story.append(Paragraph(
            f"Berichtszeitraum: {time_range[0].strftime('%d.%m.%Y %H:%M')} - "
            f"{time_range[1].strftime('%d.%m.%Y %H:%M')}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, LayoutConstants.SMALL_SPACER))
        
        # Anzahl Sensoren
        story.append(Paragraph(
            f"Anzahl Sensoren: {len(data['sensors'])}",
            self.styles['Normal']
        ))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Sensor-Übersicht
        story.append(Paragraph("Sensor-Übersicht", self.styles['CustomHeading1']))
        story.extend(self._create_sensor_overview_table(data))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Gesamtstatistiken
        story.append(Paragraph("Gesamtstatistiken", self.styles['CustomHeading1']))
        story.extend(self._create_comprehensive_statistics(data))
        
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
        
        # Titel
        story.append(Paragraph(f"Sensor {sensor_path} - Detailanalyse", self.styles['CustomTitle']))
        story.append(Spacer(1, LayoutConstants.STANDARD_SPACER))
        
        # Statistiken
        story.extend(self._create_sensor_statistics(sensor_data))
        story.append(PageBreak())

        # Aktuelle Messwerte
        story.append(Paragraph("Aktuelle Messwerte", self.styles['CustomHeading2']))
        story.extend(self._create_sensor_values_table(sensor_data[:LayoutConstants.MAX_RECENT_VALUES]))
        
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
        
        # Hauptmetriken und Luftqualität
        main_available = [m for m in MetricRegistry.MAIN_METRICS if m in available_metrics]
        if main_available:
            story.append(Paragraph("Hauptmetriken und Luftqualität", self.styles['CustomHeading2']))
            story.extend(self._create_metrics_table(all_data, main_available))
            story.append(Spacer(1, LayoutConstants.SMALL_SPACER + 5))
        
        # Weitere Metriken
        other_available = [m for m in MetricRegistry.OTHER_METRICS if m in available_metrics]
        if other_available:
            story.append(Paragraph("Weitere Metriken", self.styles['CustomHeading2']))
            story.extend(self._create_metrics_table(all_data, other_available))
            story.append(Spacer(1, LayoutConstants.SMALL_SPACER + 5))
        
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
                latest.ts_collected.strftime('%d.%m.%Y %H:%M'),
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
        
        # Hauptmetriken und Luftqualität
        main_available = [m for m in MetricRegistry.MAIN_METRICS if m in available_metrics]
        if main_available:
            story.append(Paragraph("Hauptmetriken und Luftqualität", self.styles['CustomHeading2']))
            story.extend(self._create_sensor_metrics_table(sensor_data, main_available))
            story.append(Spacer(1, LayoutConstants.SMALL_SPACER + 5))
        
        # Weitere Metriken
        other_available = [m for m in MetricRegistry.OTHER_METRICS if m in available_metrics]
        if other_available:
            story.append(Paragraph("Weitere Metriken", self.styles['CustomHeading2']))
            story.extend(self._create_sensor_metrics_table(sensor_data, other_available))
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
        """Erstellt eine Tabelle mit aktuellen Messwerten."""
        if not sensor_data:
            return []
        
        available_metrics = MetricRegistry.get_available_metrics(sensor_data)
        display_metrics = [m for m in MetricRegistry.MAIN_METRICS + MetricRegistry.OTHER_METRICS 
                          if m in available_metrics]
        
        if not display_metrics:
            return []
        
        # Tabelle-Header
        headers = ['Zeit'] + [MetricRegistry.get_definition(m).title for m in display_metrics]
        table_data = [headers]
        
        # Daten für jede Zeile
        for record in sensor_data:
            row = [record.ts_collected.strftime('%d.%m %H:%M')]
            
            for metric in display_metrics:
                value = self._extract_sensor_value(record.decoded_data, metric)
                row.append(self._format_sensor_value(value, metric))
            
            table_data.append(row)
        
        if len(table_data) > 1:
            num_metrics = len(display_metrics)
            
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