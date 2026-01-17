"""CLI commands for hermine downloader."""
import click
import asyncio
import logging
from pathlib import Path
from typing import Optional

from src.config import Config
from src.logger import setup_logger
from src.api.hermine_client import HermineClient
from src.storage.database import ManifestDB
from src.storage.path_builder import PathBuilder

logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Hermine Media Downloader CLI"""
    pass


@cli.command()
@click.option('--env', type=click.Path(), help='Pfad zu .env Datei')
def list_channels(env: Optional[str]):
    """Liste alle Kanäle mit IDs auf"""
    try:
        config = Config(Path(env) if env else None)
        setup_logger(config)

        logger.info("Verbinde zu Hermine...")
        hermine = HermineClient(
            config.hermine.base_url,
            config.hermine.username,
            config.hermine.password
        )

        channels = hermine.get_channels()

        click.secho("\n📋 Verfügbare Kanäle:\n", fg='green', bold=True)
        for i, channel in enumerate(channels, 1):
            click.echo(f"  {i}. {channel.get('name', 'Unbekannt')}")
            click.secho(f"     ID: {channel.get('id')}", fg='cyan')
            if channel.get('description'):
                click.echo(f"     Beschreibung: {channel.get('description')}")
            click.echo(f"     Mitglieder: {channel.get('member_count', 'N/A')}")
            click.echo()

        click.secho(f"Insgesamt: {len(channels)} Kanäle", fg='green')

        # Zeige wie man in .env konfiguriert
        channel_ids = ','.join([str(ch.get('id')) for ch in channels[:3]])
        click.secho(f"\nZum Konfigurieren in .env:", fg='yellow')
        click.echo(f"TARGET_CHANNELS={channel_ids}")

    except Exception as e:
        click.secho(f"❌ Fehler: {e}", fg='red')
        raise click.Abort()


@cli.command()
@click.argument('channel_id')
@click.option('--env', type=click.Path(), help='Pfad zu .env Datei')
def list_senders(channel_id: str, env: Optional[str]):
    """Liste alle Absender in einem Kanal auf"""
    try:
        config = Config(Path(env) if env else None)
        setup_logger(config)

        logger.info(f"Lade Nachrichten von Kanal {channel_id}...")
        hermine = HermineClient(
            config.hermine.base_url,
            config.hermine.username,
            config.hermine.password
        )

        # Get media files to extract sender information
        media_files = asyncio.run(hermine.get_media_files(channel_id))

        senders = {}
        for media_file in media_files:
            if media_file.sender_id and media_file.sender_name:
                if media_file.sender_id not in senders:
                    senders[media_file.sender_id] = {
                        'name': media_file.sender_name,
                        'count': 0
                    }
                senders[media_file.sender_id]['count'] += 1

        click.secho(f"\n👥 Absender im Kanal {channel_id}:\n", fg='green', bold=True)

        sorted_senders = sorted(senders.items(), key=lambda x: x[1]['count'], reverse=True)
        for i, (sender_id, info) in enumerate(sorted_senders, 1):
            click.echo(f"  {i}. {info['name']}")
            click.secho(f"     ID: {sender_id}", fg='cyan')
            click.echo(f"     Nachrichten: {info['count']}")
            click.echo()

        if sorted_senders:
            click.secho(f"Insgesamt: {len(senders)} Absender", fg='green')

    except Exception as e:
        click.secho(f"❌ Fehler: {e}", fg='red')
        raise click.Abort()


@cli.command()
@click.option('--channel', help='Nur ein Kanal (optional)')
@click.option('--env', type=click.Path(), help='Pfad zu .env Datei')
def stats(channel: Optional[str], env: Optional[str]):
    """Zeige Download-Statistiken"""
    try:
        config = Config(Path(env) if env else None)
        setup_logger(config)

        db = ManifestDB(config.storage.base_dir / "manifest.db")
        db.initialize()

        stats_dict = db.get_statistics()

        click.secho("\n📊 Download-Statistiken:\n", fg='green', bold=True)
        click.echo(f"  Dateien gesamt:    {stats_dict['total_files']}")
        click.echo(f"  Größe:             {stats_dict['total_size'] / 1024 / 1024:.2f} MB")
        click.echo(f"  Kanäle:            {stats_dict['channels']}")
        click.echo(f"  Absender:          {stats_dict['senders']}")
        click.echo(f"  Fehler:            {stats_dict['errors']}")

        # Kanal-Übersicht
        channels_stats = db.get_files_by_channel()
        if channels_stats:
            click.secho(f"\n  Nach Kanal:", fg='cyan')
            for ch_id, count in sorted(channels_stats.items(), key=lambda x: x[1], reverse=True):
                click.echo(f"    {ch_id}: {count} Dateien")

        # Absender-Übersicht
        if channel:
            senders_stats = db.get_files_by_sender(channel)
        else:
            senders_stats = db.get_files_by_sender()

        if senders_stats:
            click.secho(f"\n  Nach Absender:", fg='cyan')
            for sender, count in sorted(senders_stats.items(), key=lambda x: x[1], reverse=True)[:10]:
                click.echo(f"    {sender}: {count} Dateien")

    except Exception as e:
        click.secho(f"❌ Fehler: {e}", fg='red')
        raise click.Abort()


@cli.command()
@click.option('--env', type=click.Path(), help='Pfad zu .env Datei')
def show_template_help(env: Optional[str]):
    """Zeige Hilfe für PATH_TEMPLATE"""
    help_text = PathBuilder.get_template_help()
    click.echo(help_text)


if __name__ == '__main__':
    cli()
