#!/usr/bin/env python3
"""Hermine Media Downloader - Main Entry Point"""

import asyncio
import sys
import logging
from pathlib import Path

from src.config import Config
from src.logger import setup_logger
from src.api.hermine_client import HermineClient
from src.api.nextcloud_client import NextcloudClient
from src.storage.database import ManifestDB
from src.downloader.engine import DownloadEngine

logger = logging.getLogger(__name__)


async def main():
    """Hauptprogramm"""
    try:
        # Lade Konfiguration
        config = Config()
        setup_logger(config)

        logger.info("=" * 70)
        logger.info("🚀 Hermine Media Downloader startet...")
        logger.info("=" * 70)
        logger.info(f"Config: {config.to_dict()}")

        # Initialisiere Datenbank
        db = ManifestDB(config.storage.base_dir / "manifest.db")
        db.initialize()

        # Hermine Client
        logger.info(f"\n🔗 Verbinde zu {config.hermine.base_url}...")
        hermine = HermineClient(
            config.hermine.base_url,
            config.hermine.username,
            config.hermine.password,
            timeout=config.hermine.timeout,
            verify_ssl=config.hermine.verify_ssl
        )

        # Nextcloud Client (optional)
        nextcloud = None
        if config.nextcloud.enabled:
            logger.info(f"☁️  Nextcloud Integration: {config.nextcloud.url}")
            nextcloud = NextcloudClient(
                config.nextcloud.url,
                config.nextcloud.username,
                config.nextcloud.password,
                config.nextcloud.remote_path
            )

        # Download Engine
        engine = DownloadEngine(config, hermine, db, nextcloud)

        # Verarbeite Kanäle
        if not config.target_channels:
            logger.warning("⚠️  Keine Kanäle konfiguriert in TARGET_CHANNELS")
            logger.info("💡 Tipp: Nutze 'python3 -m src.cli list-channels' um IDs zu sehen")
            return

        total_stats = {
            'channels': 0,
            'total_downloaded': 0,
            'total_skipped': 0,
            'total_errors': 0,
            'total_size': 0
        }

        for channel_id in config.target_channels:
            try:
                stats = await engine.process_channel(channel_id)
                total_stats['channels'] += 1
                total_stats['total_downloaded'] += stats['downloaded']
                total_stats['total_skipped'] += stats['skipped']
                total_stats['total_errors'] += stats['errors']
                total_stats['total_size'] += stats['total_size']

            except Exception as e:
                logger.error(f"Fehler bei Kanal {channel_id}: {e}")
                total_stats['total_errors'] += 1

        # Statistiken anzeigen
        engine.print_statistics()

        logger.info("\n" + "=" * 70)
        logger.info("✅ Abgeschlossen!")
        logger.info("=" * 70)
        logger.info(f"  Kanäle verarbeitet: {total_stats['channels']}")
        logger.info(f"  Dateien heruntergeladen: {total_stats['total_downloaded']}")
        logger.info(f"  Übersprungen: {total_stats['total_skipped']}")
        logger.info(f"  Fehler: {total_stats['total_errors']}")
        logger.info(f"  Gesamt-Größe: {total_stats['total_size'] / 1024 / 1024:.2f} MB")
        logger.info("=" * 70)

    except KeyboardInterrupt:
        logger.warning("\n⏹️  Abbruch durch Benutzer")
        sys.exit(130)

    except Exception as e:
        logger.error(f"\n❌ Fataler Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
