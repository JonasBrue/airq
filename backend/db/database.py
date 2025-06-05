"""
Datenbank-Konfiguration und -Verbindung für das air-Q Backend.

Dieses Modul verwaltet die SQLAlchemy-Engine, Sessions und 
Datenbankinitialisierung mit async/await Support.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    async_sessionmaker, 
    create_async_engine,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base

from ..config import settings

# Logger konfigurieren
logger = logging.getLogger(__name__)

# SQLAlchemy Base Model
Base = declarative_base()

# Engine & Session Setup
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,  # Bei Bedarf auf True für SQL-Logs
    pool_pre_ping=True,  # Verbindungstest bei Checkout
    pool_recycle=3600,   # Verbindungen nach 1h recyceln
)

async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, 
    expire_on_commit=False,
    class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency für FastAPI um eine Datenbank-Session zu erhalten.
    
    Yields:
        AsyncSession: Eine aktive Datenbank-Session
        
    Example:
        @app.get("/data")
        async def get_data(session: AsyncSession = Depends(get_session)):
            # Session verwenden...
    """
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Datenbank-Session Fehler: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialisiert die Datenbank und erstellt alle Tabellen.
    
    Diese Funktion wird beim Anwendungsstart aufgerufen und erstellt
    alle in den Models definierten Tabellen, falls sie noch nicht existieren.
    
    Raises:
        Exception: Bei Problemen mit der Datenbankverbindung oder -erstellung
    """
    try:
        async with engine.begin() as conn:
            logger.info("Erstelle Datenbank-Tabellen...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Datenbank erfolgreich initialisiert")
    except Exception as e:
        logger.error(f"Fehler bei Datenbankinitialisierung: {e}")
        raise


async def close_db() -> None:
    """
    Schließt die Datenbankverbindung ordnungsgemäß.
    
    Sollte beim Anwendungsende aufgerufen werden.
    """
    try:
        await engine.dispose()
        logger.info("Datenbankverbindung geschlossen")
    except Exception as e:
        logger.error(f"Fehler beim Schließen der Datenbankverbindung: {e}")
        raise 