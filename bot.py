"""
=============================================================================
             JK DOWN BOT - TODUS & TELEGRAM HIGH-SPEED BRIDGE
  Configuración 100% integrada internamente sin depender de variables Railway
  Sistema de Respaldo y Restauración Automático para Migración de Servidor
=============================================================================
"""
from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import logging
import mimetypes
import os
import re
import socket
import tempfile
import textwrap
import time
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from urllib.parse import quote, quote_plus, urljoin, urlsplit

import aiohttp
from aiohttp.abc import AbstractResolver
from telegram import (
    BotCommand,
    CopyTextButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaDocument,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)
from telethon import TelegramClient, events
try:
    from platform_downloads import is_supported_platform_url, download_platform_video
except ImportError:
    def is_supported_platform_url(url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower()
        return any(d in host for d in ("youtube.com", "youtu.be", "facebook.com", "fb.watch", "tiktok.com", "instagram.com", "twitter.com", "x.com"))
    download_platform_video = None


# ═══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN EMBEBIDA (VALORES INTEGRADOS DIRECTAMENTE)
#  No necesitas configurar ninguna variable en Railway / VPS / Hosting.
# ═══════════════════════════════════════════════════════════════
TODUS_BASE_URL = os.getenv("TODUS_BASE_URL", "https://s3.todus.cu/stream")
TMPDIR = os.getenv("TMPDIR", "/tmp")
# Las credenciales se leen exclusivamente desde secretos del entorno.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TOKEN_BOT_DE_TELEGRAM = TELEGRAM_BOT_TOKEN
TELEGRAM_BACKUP_CHAT_ID = os.getenv("TELEGRAM_BACKUP_CHAT_ID", os.getenv("BACKUP_CHAT_ID", "")).strip()
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0") or 0)
ID_API_TELEGRAM = TELEGRAM_API_ID
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
REQUIRED_GROUP = os.getenv("REQUIRED_GROUP", "@videogameplay0406")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@gg_no_root")
OWNER_TELEGRAM_ID = int(os.getenv("OWNER_TELEGRAM_ID", "0") or 0)
MAX_TRANSFER_HOURS = int(os.getenv("MAX_TRANSFER_HOURS", "24") or 24)
MAX_FILE_MB_PREMIUM = int(os.getenv("MAX_FILE_MB_PREMIUM", "0") or 0)
MAX_FILE_MB_FREE = int(os.getenv("MAX_FILE_MB_FREE", "2048") or 2048)
MAX_CONCURRENT_UPLOADS = int(os.getenv("MAX_CONCURRENT_UPLOADS", "2") or 2)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
GROUP_JOIN_URL = os.getenv("GROUP_JOIN_URL", "https://t.me/videogameplay0406")
BOT_DATA_DIR = os.getenv("BOT_DATA_DIR", "./data")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(Path(BOT_DATA_DIR) / "premium.sqlite3"))
CHANNEL_JOIN_URL = os.getenv("CHANNEL_JOIN_URL", "https://t.me/gg_no_root")
# Configurar logging con el nivel embebido
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("jk-telegram-bot")

# Directorios de soporte garantizados
os.makedirs(TMPDIR, exist_ok=True)
os.makedirs(os.path.dirname(DATABASE_PATH) or "./data", exist_ok=True)

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
URL_MAX_CHARS = 2048
MIB = 1024 ** 2
GIB = 1024 ** 3
BOT_API_DOWNLOAD_LIMIT = 20 * MIB

# ═══════════════════════════════════════════════════════════════
#  IDENTIDAD Y FUENTE SMALL CAPS
# ═══════════════════════════════════════════════════════════════
BOT_NAME = "ᴊᴋ ᴅᴏᴡɴ ʙᴏᴛꫂꤪꤨᴼᶠᶜ"
BOT_CREATOR = "@jakudoshy"
BOT_FOOTER = ""  # Desactivado para no terminar con el nombre del bot
PLAN_ADMIN_USERNAME = "jakudoshy"
HIDDEN_OWNER_ID = OWNER_TELEGRAM_ID

_SMALL_CAPS_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ",
    "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
    "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "q", "r": "ʀ",
    "s": "ꜱ", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
    "y": "ʏ", "z": "ᴢ",
    "á": "ᴀ́", "é": "ᴇ́", "í": "ɪ́", "ó": "ᴏ́", "ú": "ᴜ́",
    "ñ": "ɴ̃", "ü": "ᴜ̈",
}
_SMALL_CAPS_FULL = {}
for k, v in _SMALL_CAPS_MAP.items():
    _SMALL_CAPS_FULL[k] = v
    _SMALL_CAPS_FULL[k.upper()] = v

SMALL_CAPS = str.maketrans(_SMALL_CAPS_FULL)

PRESERVED_UI_TOKEN = re.compile(
    r"(https?://[^\s<>]+|@[a-zA-Z0-9_]+|\x00[^\x00]+\x00|<[^>]+>|\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b|/[a-zA-Z0-9_]+|\b\d+\b)"
)


def sc(value: str) -> str:
    """Convierte texto a small caps (estilo ᴇѕᴛᴇ) preservando enlaces, comandos, números, tags y @usuarios."""
    if not value:
        return value
    chunks = PRESERVED_UI_TOKEN.split(str(value))
    result = []
    for index, chunk in enumerate(chunks):
        if index % 2:
            result.append(chunk)
        else:
            result.append(chunk.translate(SMALL_CAPS))
    return "".join(result)


PROTECTED_PATTERN = re.compile(r"(<[^>]+>|\{mono:[^}]+})")


def card(title: str, lines: list[str] | tuple[str, ...]) -> str:
    """Genera tarjetas estéticas con recuadro futurista cerrado:
    - Arriba izquierda: ┎ <b>{header_title}</b>
    - Separador: ┠──────────────────────
    - Líneas con texto o letras: ┠ 
    - Líneas vacías: ┃ (línea vertical gruesa del mismo grosor que ┎, ┠ y ┖)
    - Abajo izquierda (última línea de contenido): ┖ {último_texto}
    - Nada queda afuera del recuadro ni lo rompe.
    - Tipografía estilizada ᴇѕᴛᴇ preservando enlaces y menciones.
    """
    header_title = sc(title) if "<" not in title else title
    flat_lines = []
    for item in lines:
        if item is None:
            flat_lines.append("")
        elif isinstance(item, str) and chr(10) in item:
            flat_lines.extend(item.split(chr(10)))
        else:
            flat_lines.append(str(item))

    raw_items = []
    for line in flat_lines:
        line_str = str(line)
        clean_check = line_str.strip()
        if not clean_check or clean_check in {"┃", "│", "|", "┠", "┠──────────────────────", "----------------------"}:
            raw_items.append("┃")
            continue
        protected_parts = []

        def _save_protected(match):
            token = match.group(0)
            if token.startswith("{mono:") and token.endswith("}"):
                val = token[6:-1]
                protected_parts.append(f"<code>{html.escape(val, quote=False)}</code>")
            else:
                protected_parts.append(token)
            return f"\x00__{len(protected_parts) - 1}__\x00"

        protected = PROTECTED_PATTERN.sub(_save_protected, line_str)
        for i_idx, val in enumerate(protected_parts):
            protected = protected.replace(f"\x00__{i_idx}__\x00", val)

        clean_line = protected.strip()
        if not clean_line or clean_line in {"┃", "│", "|"}:
            raw_items.append("┃")
        else:
            if clean_line.startswith("┠ "):
                clean_line = clean_line[2:].strip()
            elif clean_line.startswith("┠"):
                clean_line = clean_line[1:].strip()
            elif clean_line.startswith("┖ "):
                clean_line = clean_line[2:].strip()
            elif clean_line.startswith("┖"):
                clean_line = clean_line[1:].strip()
            elif clean_line.startswith("|- "):
                clean_line = clean_line[3:].strip()
            elif clean_line.startswith("|-"):
                clean_line = clean_line[2:].strip()
            raw_items.append(sc(clean_line))

    while raw_items and raw_items[-1] == "┃":
        raw_items.pop()

    last_content_idx = -1
    for i in range(len(raw_items) - 1, -1, -1):
        if raw_items[i] != "┃":
            last_content_idx = i
            break

    out = [f"┎ <b>{header_title}</b>", "┠──────────────────────"]
    for i, it in enumerate(raw_items):
        if it == "┃":
            out.append("┃")
        elif i == last_content_idx:
            out.append(f"┖ {it}")
        else:
            out.append(f"┠ {it}")

    return "\n".join(out)


def card_with_credit(title: str, lines: list[str] | tuple[str, ...]) -> str:
    return card(title, lines)



# ═══════════════════════════════════════════════════════════════
#  SISTEMA DE PLANES, PRECIOS Y DURACIONES
# ═══════════════════════════════════════════════════════════════
PLANS = {
    "free": {
        "name": "ɢʀᴀᴛɪꜱ",
        "display": "Plan Gratis",
        "daily_bytes": (MAX_FILE_MB_FREE * MIB) if MAX_FILE_MB_FREE > 0 else (5 * GIB),
        "daily_label": f"{MAX_FILE_MB_FREE / 1024:.2f} GB" if MAX_FILE_MB_FREE > 0 else "2.00 GB",
        "badge": "🆓",
        "rank": 0,
        "price": "0$",
        "price_value": 0,
        "storage_hours": 12,
        "storage_label": "12 horas",
        "quota_period_days": 1,
    },
    "premium": {
        "name": "ᴘʀᴇᴍɪᴜᴍ",
        "display": "Plan Premium",
        "daily_bytes": 10 * GIB,
        "daily_label": "10.00 GB",
        "badge": "👑",
        "rank": 1,
        "price": "250$",
        "price_value": 250,
        "storage_hours": 72,
        "storage_label": "72 horas",
        "quota_period_days": 1,
    },
    "vip": {
        "name": "ᴠɪᴘ",
        "display": "Plan VIP",
        "daily_bytes": 25 * GIB,
        "daily_label": "25.00 GB",
        "badge": "⭐",
        "rank": 2,
        "price": "500$",
        "price_value": 500,
        "storage_hours": 24,
        "storage_label": "24 horas",
        "quota_period_days": 1,
    },
    "vip_basic": {
        "name": "ᴠɪᴘ",
        "display": "Plan VIP",
        "daily_bytes": 25 * GIB,
        "daily_label": "25.00 GB",
        "badge": "⭐",
        "rank": 2,
        "price": "500$",
        "price_value": 500,
        "storage_hours": 24,
        "storage_label": "24 horas",
        "quota_period_days": 1,
    },
    "vip_medium": {
        "name": "ᴠɪᴘ ᴍᴇᴅɪᴏ",
        "display": "VIP Medio",
        "daily_bytes": 35 * GIB,
        "daily_label": "35.00 GB",
        "badge": "💎",
        "rank": 3,
        "price": "750$",
        "price_value": 750,
        "storage_hours": 48,
        "storage_label": "48 horas",
        "quota_period_days": 1,
    },
    "ultra": {
        "name": "ᴜʟᴛʀᴀ",
        "display": "Plan Ultra",
        "daily_bytes": float('inf'),
        "daily_label": "Ilimitado (∞ GB)",
        "badge": "🔥",
        "rank": 4,
        "price": "1000$",
        "price_value": 1000,
        "storage_hours": 72,
        "storage_label": "72 horas",
        "quota_period_days": 1,
    },
    "owner": {
        "name": "ᴄʀᴇᴀᴅᴏʀ",
        "display": "Plan Creador",
        "daily_bytes": float('inf'),
        "daily_label": "∞ GB",
        "badge": "🜲",
        "rank": 999,
        "price": "∞",
        "price_value": 0,
        "storage_hours": 72,
        "storage_label": "72 horas",
        "quota_period_days": 1,
    },
}

PLAN_QUEUE_LIMITS = {
    "free": 2,
    "premium": 6,
    "vip": 10,
    "vip_basic": 10,
    "vip_medium": 15,
    "ultra": 30,
    "owner": 10**9,
}


# ═══════════════════════════════════════════════════════════════
#  ALMACENAMIENTO PERSISTENTE Y DEFINICIÓN DE ARCHIVOS
# ═══════════════════════════════════════════════════════════════
def _get_data_dir() -> Path:
    candidates = [
        os.getenv("BOT_DATA_DIR", ""),
        os.path.dirname(DATABASE_PATH) or "./data",
        "/data",
        str(Path.home() / ".jk_bot"),
        str(Path(tempfile.gettempdir()) / "jk_bot"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            path = Path(candidate)
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            return path
        except Exception:
            continue
    return Path(".")


DATA_DIR = _get_data_dir()
PLAN_DATA_FILE = str(DATA_DIR / "user_plans.json")
REFERRAL_START_BALANCE = 5
REFERRAL_REWARD = 10
USAGE_DATA_FILE = str(DATA_DIR / "daily_usage.json")
HISTORY_DATA_FILE = str(DATA_DIR / "task_history.json")
USERS_DATA_FILE = str(DATA_DIR / "users.json")
ADMIN_AUDIT_FILE = str(DATA_DIR / "admin_audit.json")
TELEGRAM_AUTH_DIR = DATA_DIR / "telegram_auth"
CLOUD_CACHE_DIR = DATA_DIR / "cloud_cache"
CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
#  MOTOR DE RESPALDO Y RESTAURACIÓN EN TELEGRAM (PARA MIGRACIÓN)
# ═══════════════════════════════════════════════════════════════
@dataclass
class BackupLayout:
    data_dir: Path
    auth_dir: Path
    files_map: dict

    @classmethod
    def from_paths(cls, data_dir: Path | str, auth_dir: Path | str, files_map: dict) -> BackupLayout:
        return cls(Path(data_dir), Path(auth_dir), files_map)


def telegram_backup_layout() -> BackupLayout:
    return BackupLayout.from_paths(
        DATA_DIR,
        TELEGRAM_AUTH_DIR,
        {
            "user_plans.json": PLAN_DATA_FILE,
            "daily_usage.json": USAGE_DATA_FILE,
            "task_history.json": HISTORY_DATA_FILE,
            "users.json": USERS_DATA_FILE,
            "admin_audit.json": ADMIN_AUDIT_FILE,
            "premium.sqlite3": DATABASE_PATH,
        },
    )


def configured_backup_chat_id() -> str:
    return str(TELEGRAM_BACKUP_CHAT_ID).strip()


async def backup_to_telegram(
    bot_obj,
    bot_token: str,
    chat_id: str | int,
    layout: BackupLayout,
    logger: logging.Logger | None = None,
) -> bool:
    """Empaqueta toda la base de datos en un ZIP y lo envía/fija en el canal de respaldo."""
    log_inst = logger or log
    if not chat_id:
        return False
    temp_zip = None
    try:
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        zip_filename = f"backup_jk_bot_{now_str}.zip"
        temp_fd, temp_zip_path = tempfile.mkstemp(prefix="jk_backup_", suffix=".zip", dir=TMPDIR)
        os.close(temp_fd)
        temp_zip = Path(temp_zip_path)

        files_to_pack: list[tuple[Path, str]] = []
        for arcname, filepath in layout.files_map.items():
            fpath = Path(filepath)
            if fpath.exists() and fpath.is_file() and fpath.stat().st_size > 0:
                files_to_pack.append((fpath, arcname))

        if layout.data_dir.exists():
            for item in layout.data_dir.glob("*"):
                if item.is_file() and not item.name.endswith(".tmp"):
                    if not any(item.resolve() == p.resolve() for p, _ in files_to_pack):
                        files_to_pack.append((item, item.name))
            # El caché es necesario para que Cloud Guardian pueda restaurar un
            # objeto borrado después de un redeploy. Se guarda junto al historial.
            cache_dir = layout.data_dir / "cloud_cache"
            if cache_dir.exists():
                for item in cache_dir.rglob("*"):
                    if item.is_file() and not item.name.endswith(".tmp"):
                        files_to_pack.append((item, f"cloud_cache/{item.relative_to(cache_dir).as_posix()}"))

        if layout.auth_dir.exists():
            for item in layout.auth_dir.rglob("*"):
                if item.is_file() and not item.name.endswith(".tmp"):
                    files_to_pack.append((item, f"telegram_auth/{item.relative_to(layout.auth_dir).as_posix()}"))

        if not files_to_pack:
            return False

        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "bot": "JK DOWN BOT",
                "files": [arcname for _, arcname in files_to_pack],
            }
            zf.writestr("backup_manifest.json", json.dumps(manifest, indent=2))
            for fpath, arcname in files_to_pack:
                try:
                    zf.write(fpath, arcname=arcname)
                except Exception:
                    pass

        total_bytes = temp_zip.stat().st_size
        caption = (
            f"📦 <b>JK DOWN BOT · RESPALDO DE DATOS</b>\n\n"
            f"📅 <b>Fecha:</b> {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S UTC')}\n"
            f"💾 <b>Tamaño:</b> {total_bytes / 1024:.1f} KB\n"
            f"🗂️ <b>Archivos:</b> {len(files_to_pack)}\n\n"
            f"<i>Respaldo automático listo para restaurar datos en caso de migración de hosting.</i>"
        )

        with temp_zip.open("rb") as doc:
            # Localizador de mensaje fijado para editar el mismo archivo en vez de enviar repetidos
            backup_state_file = layout.data_dir / "backup_pinned_msg.json"
            target_msg_id = None
            if backup_state_file.exists():
                try:
                    target_msg_id = json.loads(backup_state_file.read_text(encoding="utf-8")).get("message_id")
                except Exception:
                    target_msg_id = None

            if not target_msg_id:
                try:
                    chat_obj = await bot_obj.get_chat(chat_id)
                    if getattr(chat_obj, "pinned_message", None):
                        target_msg_id = chat_obj.pinned_message.message_id
                except Exception:
                    pass

            edited_in_place = False
            if target_msg_id:
                try:
                    await bot_obj.edit_message_media(
                        chat_id=chat_id,
                        message_id=target_msg_id,
                        media=InputMediaDocument(
                            media=doc,
                            filename=zip_filename,
                            caption=caption,
                            parse_mode="HTML",
                        ),
                    )
                    edited_in_place = True
                    log_inst.info(f"✅ Respaldo actualizado exitosamente editando el mensaje fijado #{target_msg_id}")
                except Exception as edit_err:
                    log_inst.info(f"Aviso: no se pudo editar mensaje fijado #{target_msg_id} ({edit_err}), se enviará uno nuevo y se fijará.")

            if not edited_in_place:
                sent_msg = await bot_obj.send_document(
                    chat_id=chat_id,
                    document=doc,
                    filename=zip_filename,
                    caption=caption,
                    parse_mode="HTML",
                    disable_notification=True,
                )
                target_msg_id = sent_msg.message_id
                try:
                    await bot_obj.pin_chat_message(
                        chat_id=chat_id,
                        message_id=target_msg_id,
                        disable_notification=True,
                    )
                except Exception:
                    pass
                log_inst.info(f"✅ Nuevo respaldo enviado y fijado como #{target_msg_id}")

            try:
                backup_state_file.write_text(
                    json.dumps({"message_id": target_msg_id, "updated_at": datetime.now(timezone.utc).isoformat()}),
                    encoding="utf-8"
                )
            except Exception:
                pass

        return True
    except Exception as exc:
        log_inst.warning(f"Error generando respaldo a Telegram: {exc}")
        return False
    finally:
        if temp_zip and temp_zip.exists():
            try:
                temp_zip.unlink()
            except Exception:
                pass


async def restore_from_telegram(
    bot_obj,
    bot_token: str,
    chat_id: str | int,
    layout: BackupLayout,
    logger: logging.Logger | None = None,
) -> tuple[int, int]:
    """Restaura automáticamente los datos descargando el respaldo fijado en Telegram."""
    log_inst = logger or log
    if not chat_id:
        return 0, 0
    temp_zip = None
    try:
        log_inst.info(f"🔍 Consultando respaldo en {chat_id} para restaurar datos tras migración...")
        chat = await bot_obj.get_chat(chat_id)
        target_doc = None
        if getattr(chat, "pinned_message", None) and chat.pinned_message.document:
            target_doc = chat.pinned_message.document

        if not target_doc:
            log_inst.info("No hay mensaje fijado con documento en el canal de respaldo.")
            return 0, 0

        temp_fd, temp_zip_path = tempfile.mkstemp(prefix="restore_jk_", suffix=".zip", dir=TMPDIR)
        os.close(temp_fd)
        temp_zip = Path(temp_zip_path)

        tg_file = await target_doc.get_file()
        await tg_file.download_to_drive(custom_path=str(temp_zip))

        layout.data_dir.mkdir(parents=True, exist_ok=True)
        layout.auth_dir.mkdir(parents=True, exist_ok=True)

        restored_files = 0
        total_bytes = 0

        with zipfile.ZipFile(temp_zip, "r") as zf:
            for member in zf.infolist():
                if member.is_dir() or member.filename == "backup_manifest.json":
                    continue
                filename = member.filename
                if filename.startswith("telegram_auth/"):
                    dest = layout.auth_dir / filename.replace("telegram_auth/", "")
                else:
                    dest = layout.data_dir / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Evitar traversal y no destruir datos locales existentes.
                root = layout.auth_dir if filename.startswith("telegram_auth/") else layout.data_dir
                relative_name = filename.replace("telegram_auth/", "", 1) if filename.startswith("telegram_auth/") else filename
                dest = root / relative_name
                try:
                    dest.resolve().relative_to(root.resolve())
                except ValueError:
                    raise ValueError("Ruta insegura en el respaldo")
                if dest.exists():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(dest, "wb") as target:
                    shutil.copyfileobj(source, target)
                restored_files += 1
                total_bytes += member.file_size

        # Si la ruta absoluta del volumen cambió, reparar referencias del caché.
        history_path = Path(layout.files_map.get("task_history.json", layout.data_dir / "task_history.json"))
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
                for entries in history.values():
                    if isinstance(entries, list):
                        for entry in entries:
                            if isinstance(entry, dict) and isinstance(entry.get("cached_paths"), list):
                                entry["cached_paths"] = [str(layout.data_dir / "cloud_cache" / Path(cp).name) for cp in entry["cached_paths"]]
                history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        log_inst.info(f"✅ ¡Restauración completada con éxito! {restored_files} archivos restaurados.")
        return restored_files, total_bytes
    except Exception as exc:
        log_inst.warning(f"Restauración de respaldo no completada: {exc}")
        return 0, 0
    finally:
        if temp_zip and temp_zip.exists():
            try:
                temp_zip.unlink()
            except Exception:
                pass


async def periodic_backup(
    bot_obj,
    bot_token: str,
    chat_id: str | int,
    layout: BackupLayout,
    interval_seconds: int = 600,
    lock: asyncio.Lock | None = None,
    logger: logging.Logger | None = None,
) -> None:
    log_inst = logger or log
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            if lock:
                async with lock:
                    await backup_to_telegram(bot_obj, bot_token, chat_id, layout, logger=log_inst)
            else:
                await backup_to_telegram(bot_obj, bot_token, chat_id, layout, logger=log_inst)
        except asyncio.CancelledError:
            break
        except Exception:
            pass


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_json(path: str, data: dict) -> None:
    try:
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        tmp = path_obj.with_suffix(path_obj.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            shutil.move(str(tmp), str(path_obj))
        except (PermissionError, OSError):
            with open(path_obj, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"No se pudo guardar {path}: {e}")



# ═══════════════════════════════════════════════════════════════════════════════
# SISTEMA DE VINCULACIÓN AUTOMÁTICA CON FOTO DE PERFIL PARA JK DOWNLOADER
# ═══════════════════════════════════════════════════════════════════════════════

APP_LINKS_FILE = str(DATA_DIR / "app_links.json")

def link_user_app(token: str, user_id: int, full_name: str, username: str | None, photo_url: str | None = None) -> dict:
    code = token.strip().upper()
    data = _load_json(APP_LINKS_FILE)
    if not isinstance(data, dict):
        data = {}
    balance = get_user_balance(user_id)
    user_handle = f"@{username}" if username else ""
    user_plan_id = get_user_plan(user_id)
    plan_info = get_plan_info(user_plan_id)
    plan_badge = plan_info.get("badge", "🆓")
    plan_display = plan_info.get("display", "PLAN FREE")
    data[code] = {
        "user_id": user_id,
        "name": full_name or "Usuario Verificado JK",
        "username": user_handle,
        "telegram_id": str(user_id),
        "photo_url": photo_url,
        "status": "Verificado · Activo",
        "balance": f"{balance}$ CUP",
        "quota_plan": f"Plan: {plan_badge} {plan_display}",
        "plan_name": plan_display,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "creator": "ᴊᴀᴋᴜᴅᴏѕʜʏꫂꤪꤨᴼᶠᶜ",
        "channel": "https://t.me/gg_no_rot",
        "bot": "@downfree_jk_bot",
        "active": True
    }
    _save_json(APP_LINKS_FILE, data)
    try:
        ud = _load_json(USERS_DATA_FILE)
        if isinstance(ud, dict) and "users" in ud:
            u_entry = ud["users"].setdefault(str(user_id), {})
            u_entry["app_linked"] = True
            u_entry["app_token"] = code
            u_entry["last_app_sync"] = datetime.now(timezone.utc).isoformat()
            _save_json(USERS_DATA_FILE, ud)
    except Exception:
        pass
    return data[code]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    if not user or not update.effective_message:
        return
    if not await ensure_membership(update, context):
        return
    referral_notice = ""
    args = getattr(context, "args", []) or []
    if args:
        first_arg = str(args[0]).strip()
        # Detección de código único de start desde JK Downloader (ej: /start JK-839210)
        if first_arg.upper().startswith("JK") or first_arg.upper().startswith("LINK_JK") or first_arg.upper().startswith("APP_"):
            token_code = first_arg.upper()
            avatar_url = None
            try:
                # Obtener la foto de perfil real del usuario en Telegram
                photos = await context.bot.get_user_profile_photos(user.id, limit=1)
                if photos.total_count > 0:
                    photo_file = await context.bot.get_file(photos.photos[0][-1].file_id)
                    avatar_url = photo_file.file_path
            except Exception:
                pass

            link_user_app(
                token_code,
                user.id,
                getattr(user, "full_name", "") or getattr(user, "first_name", ""),
                getattr(user, "username", None),
                photo_url=avatar_url
            )
            user_balance = get_user_balance(user.id)
            user_handle = f"@{user.username}" if user.username else ""
            link_lines = [
                f"👤 ɴᴏᴍʙʀᴇ: {getattr(user, 'full_name', '') or getattr(user, 'first_name', '')}",
                f"🆔 ɪᴅ ᴛᴇʟᴇɢʀᴀᴍ: {mono:{user.id}}",
            ]
            if user_handle:
                link_lines.append(f"🔗 ᴜꜱᴜᴀʀɪᴏ: {user_handle}")
            link_lines.extend([
                "🛡️ ᴇꜱᴛᴀᴅᴏ: ᴠᴇʀɪꜰɪᴄᴀᴅᴏ · ᴀᴄᴛɪᴠᴏ",
                f"💳 ꜱᴀʟᴅᴏ ᴇɴ ᴄᴜᴇɴᴛᴀ: {user_balance}$ ᴄᴜᴘ",
                f"🔑 ᴄóᴅɪɢᴏ: {mono:{token_code}}",
                "",
                "✅ ¡TU SOLICITUD ESTÁ VERIFICADA CON ÉXITO!",
                "📲 Ya puedes volver a la aplicación.",
                "",
                "🚀 ᴍᴏᴅ ʙʏ ᴊᴀᴋᴜᴅᴏѕʜʏꫂꤪꤨᴼᶠᶜ",
                "📢 ᴄᴀɴᴀʟ: t.me/gg_no_rot"
            ])
            await update.effective_message.reply_text(
                card("⚡ ᴠɪɴᴄᴜʟᴀᴄɪóɴ ᴊᴋ ᴅᴏᴡɴʟᴏᴀᴅᴇʀ", link_lines),
                reply_markup=InlineKeyboardMarkup([
                    [btn("☁️ ᴠᴇʀ ᴍɪ ɴᴜʙᴇ", callback_data="history")],
                    [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]
                ]),
            )
            return

        match = re.fullmatch(r"ref_(\d+)", first_arg, re.IGNORECASE)
        if match:
            referrer_id = int(match.group(1))
            if user.id == referrer_id:
                referral_notice = "\n\n⚠️ No puedes usar tu propio enlace de invitación."
            else:
                users_data = _load_json(USERS_DATA_FILE).get("users", {})
                user_entry = users_data.get(str(user.id), {}) if isinstance(users_data, dict) else {}
                if user_entry.get("referred_by") or user_entry.get("referral_rewarded"):
                    referral_notice = "\n\n⚠️ Ya eres usuario de este bot y utilizaste un enlace de invitación anteriormente."
                elif str(user.id) in users_data and user_entry.get("first_seen"):
                    referral_notice = "\n\n⚠️ Ya eres usuario registrado de este bot. Los enlaces de invitación solo son válidos para nuevos miembros."
                elif apply_referral(user.id, referrer_id):
                    referral_notice = "\n\n🎁 Recibiste 5$ de bienvenida por entrar con un enlace de invitación."
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=card("🎉 ʀᴇꜰᴇʀɪᴅᴏ ᴄᴏɴꜰɪʀᴍᴀᴅᴏ", [
                                "Alguien entró con tu enlace.",
                                "🎊 ¡Felicidades! Recibiste 5$.",
                                f"💳 Saldo actual: {get_user_balance(referrer_id)}$",
                            ]),
                        )
                    except Exception:
                        pass
                    schedule_data_backup(context.application, "recompensa de referido")
                else:
                    referral_notice = "\n\n⚠️ Ya eres usuario de este bot o el enlace ya no es válido."
    await update.effective_message.reply_text(
        welcome_text(
            user.id,
            getattr(user, "full_name", "") or getattr(user, "first_name", ""),
            getattr(user, "username", None),
        ) + referral_notice,
        reply_markup=main_keyboard(user.id),
    )


async def vincular_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return
    if not await ensure_membership(update, context):
        return
    args = getattr(context, "args", []) or []
    if not args:
        token_sug = f"JK-{(user.id % 900000) + 100000}"
        await message.reply_text(
            card("🔗 ᴠɪɴᴄᴜʟᴀʀ ᴀᴘᴘ ᴊᴋ", [
                "Para vincular tu aplicación JK Downloader:",
                "1. Abre la app en tu teléfono.",
                "2. Toca en el menú lateral o perfil.",
                "3. Pulsa el botón azul 'ABRIR TELEGRAM'.",
                "",
                f"🔑 Tu código: {{mono:{token_sug}}}",
                "O envía en este chat:",
                f"<code>/vincular {token_sug}</code>",
                "",
                "🚀 ᴍᴏᴅ ʙʏ ᴊᴀᴋᴜᴅᴏѕʜʏꫂꤪꤨᴼᶠᶜ",
                "📢 ᴄᴀɴᴀʟ: t.me/gg_no_rot"
            ]),
            reply_markup=InlineKeyboardMarkup([[btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]]),
        )
        return
    token = str(args[0]).strip().upper()
    avatar_url = None
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            photo_file = await context.bot.get_file(photos.photos[0][-1].file_id)
            avatar_url = photo_file.file_path
    except Exception:
        pass

    link_user_app(
        token,
        user.id,
        getattr(user, "full_name", "") or getattr(user, "first_name", ""),
        getattr(user, "username", None),
        photo_url=avatar_url
    )
    user_balance = get_user_balance(user.id)
    user_handle = f"@{user.username}" if user.username else ""
    lines = [
        f"👤 ɴᴏᴍʙʀᴇ: {getattr(user, 'full_name', '') or getattr(user, 'first_name', '')}",
        f"🆔 ɪᴅ ᴛᴇʟᴇɢʀᴀᴍ: {{mono:{user.id}}}",
    ]
    if user_handle:
        lines.append(f"🔗 ᴜꜱᴜᴀʀɪᴏ: {user_handle}")
    lines.extend([
        "🛡️ ᴇꜱᴛᴀᴅᴏ: ᴠᴇʀɪꜰɪᴄᴀᴅᴏ · ᴀᴄᴛɪᴠᴏ",
        f"💳 ꜱᴀʟᴅᴏ ᴇɴ ᴄᴜᴇɴᴛᴀ: {user_balance}$ ᴄᴜᴘ",
        f"🔑 ᴄóᴅɪɢᴏ: {{mono:{token}}}",
        "",
        "✅ ¡TU SOLICITUD ESTÁ VERIFICADA CON ÉXITO!",
        "📲 Ya puedes volver a la aplicación.",
        "",
        "🚀 ᴍᴏᴅ ʙʏ ᴊᴀᴋᴜᴅᴏѕʜʏꫂꤪꤨᴼᶠᶜ",
        "📢 ᴄᴀɴᴀʟ: t.me/gg_no_rot"
    ])
    await message.reply_text(
        card("⚡ ᴠɪɴᴄᴜʟᴀᴄɪóɴ ᴇxɪᴛᴏꜱᴀ", lines),
        reply_markup=InlineKeyboardMarkup([
            [btn("☁️ ᴠᴇʀ ᴍɪ ɴᴜʙᴇ", callback_data="history")],
            [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]
        ]),
    )
    
# ═══════════════════════════════════════════════════════════════
#  GESTIÓN DE USUARIOS, PLANES Y SALDOS
# ═══════════════════════════════════════════════════════════════
def is_owner(user_id: int) -> bool:
    return user_id == OWNER_TELEGRAM_ID or user_id == HIDDEN_OWNER_ID


def register_user(user) -> None:
    if not user or is_owner(getattr(user, "id", 0)):
        return
    try:
        now = datetime.now(timezone.utc)
        users_data = _load_json(USERS_DATA_FILE)
        users = users_data.get("users", {})
        if not isinstance(users, dict):
            users = {}
        key = str(int(user.id))
        entry = users.get(key, {})
        entry.setdefault("balance", REFERRAL_START_BALANCE)
        entry.setdefault("welcome_reward", REFERRAL_START_BALANCE)
        entry.update({
            "user_id": int(user.id),
            "first_name": getattr(user, "first_name", "") or "",
            "full_name": getattr(user, "full_name", "") or "",
            "username": getattr(user, "username", None),
            "last_seen": now.isoformat(),
            "last_seen_date": now.strftime("%Y-%m-%d"),
        })
        entry.setdefault("first_seen", now.isoformat())
        users[key] = entry
        users_data["users"] = users
        _save_json(USERS_DATA_FILE, users_data)
    except Exception:
        pass


def get_user_balance(user_id: int) -> int:
    if is_owner(user_id):
        return 0
    users = _load_json(USERS_DATA_FILE).get("users", {})
    entry = users.get(str(user_id), {}) if isinstance(users, dict) else {}
    try:
        return max(0, int(entry.get("balance", REFERRAL_START_BALANCE)))
    except (TypeError, ValueError):
        return REFERRAL_START_BALANCE


def purchase_plan_with_balance(user_id: int, plan_key: str) -> tuple[bool, str]:
    plan = PLANS.get(plan_key)
    if not plan or plan_key in {"free", "owner"}:
        return False, "Ese plan no se puede comprar desde este menú."
    price = int(plan.get("price_value", 0))
    if price <= 0:
        return False, "Ese plan no tiene un precio de compra."
    try:
        data = _load_json(USERS_DATA_FILE)
        users = data.get("users", {})
        entry = users.get(str(user_id))
        if not isinstance(entry, dict):
            return False, "No se encontró tu cuenta. Abre /start e inténtalo de nuevo."
        balance = max(0, int(entry.get("balance", REFERRAL_START_BALANCE)))
        if balance < price:
            return False, f"Saldo insuficiente: necesitas {price}$ y tienes {balance}$."
        entry["balance"] = balance - price
        entry["last_plan_purchase"] = {
            "plan": plan_key,
            "price": price,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        users[str(user_id)] = entry
        data["users"] = users
        _save_json(USERS_DATA_FILE, data)
        set_user_plan(user_id, plan_key)
        return True, "Compra confirmada y plan activado correctamente."
    except Exception:
        return False, "No se pudo guardar la compra. Inténtalo de nuevo."


def grant_user_balance(user_id: int, amount: int) -> tuple[bool, int]:
    if user_id <= 0 or amount <= 0:
        return False, 0
    try:
        data = _load_json(USERS_DATA_FILE)
        users = data.get("users", {})
        if not isinstance(users, dict):
            users = {}
        entry = users.get(str(user_id), {})
        if not isinstance(entry, dict):
            entry = {}
        current = max(0, int(entry.get("balance", REFERRAL_START_BALANCE)))
        entry.update({"user_id": user_id, "balance": current + amount})
        entry["balance_granted_at"] = datetime.now(timezone.utc).isoformat()
        users[str(user_id)] = entry
        data["users"] = users
        _save_json(USERS_DATA_FILE, data)
        return True, current + amount
    except Exception:
        return False, 0


def referral_link(user_id: int, bot_username: str | None = None) -> str:
    username = (bot_username or "Downfree_jk_bot").strip().lstrip("@")
    return f"https://t.me/{username}?start=ref_{int(user_id)}"


def apply_referral(user_id: int, referrer_id: int) -> bool:
    if user_id <= 0 or referrer_id <= 0 or user_id == referrer_id or is_owner(user_id):
        return False
    try:
        data = _load_json(USERS_DATA_FILE)
        users = data.get("users", {})
        if not isinstance(users, dict) or str(user_id) not in users or str(referrer_id) not in users:
            return False
        invited = users[str(user_id)]
        if invited.get("referred_by") or invited.get("referral_rewarded"):
            return False
        inviter = users[str(referrer_id)]
        inviter["balance"] = max(0, int(inviter.get("balance", REFERRAL_START_BALANCE))) + REFERRAL_REWARD
        invited["referred_by"] = referrer_id
        invited["referral_rewarded"] = True
        invited["referral_reward"] = REFERRAL_START_BALANCE
        data["users"] = users
        _save_json(USERS_DATA_FILE, data)
        return True
    except Exception:
        return False


def registered_user_ids() -> list[int]:
    ids: set[int] = set()
    users = _load_json(USERS_DATA_FILE).get("users", {})
    if isinstance(users, dict):
        ids.update(int(uid) for uid in users if str(uid).lstrip("-").isdigit())
    for path in (PLAN_DATA_FILE, USAGE_DATA_FILE, HISTORY_DATA_FILE):
        data = _load_json(path)
        ids.update(int(uid) for uid in data if str(uid).lstrip("-").isdigit())
    return sorted(uid for uid in ids if not is_owner(uid) and uid > 0)


def get_user_plan_entry(user_id: int) -> dict:
    if is_owner(user_id):
        return {"plan": "owner", "assigned_at": datetime.now(timezone.utc).isoformat()}
    try:
        data = _load_json(PLAN_DATA_FILE)
        entry = data.get(str(user_id), {"plan": "free"})
        if entry.get("plan") != "free" and "expires_at" in entry:
            try:
                expires = datetime.fromisoformat(entry["expires_at"])
                if datetime.now(timezone.utc) > expires:
                    entry = {"plan": "free", "assigned_at": datetime.now(timezone.utc).isoformat()}
                    data[str(user_id)] = entry
                    _save_json(PLAN_DATA_FILE, data)
            except Exception:
                pass
        return entry
    except Exception:
        return {"plan": "free"}


def get_user_plan(user_id: int) -> str:
    return get_user_plan_entry(user_id).get("plan", "free")


def get_user_queue_limit(user_id: int) -> int:
    if is_owner(user_id):
        return PLAN_QUEUE_LIMITS["owner"]
    return PLAN_QUEUE_LIMITS.get(get_user_plan(user_id), PLAN_QUEUE_LIMITS["free"])


def get_plan_expiry_info(user_id: int) -> tuple[str | None, int | None]:
    if is_owner(user_id):
        return None, None
    entry = get_user_plan_entry(user_id)
    expires = entry.get("expires_at")
    if not expires:
        return None, None
    try:
        dt = datetime.fromisoformat(expires)
        now = datetime.now(timezone.utc)
        rem_days = max(0, (dt - now).days + (1 if (dt - now).seconds > 0 else 0))
        return dt.strftime("%d/%m/%Y"), rem_days
    except Exception:
        return None, None


def set_user_plan(user_id: int, plan_key: str, days: int | None = None) -> dict:
    now = datetime.now(timezone.utc)
    entry = {
        "plan": plan_key,
        "assigned_at": now.isoformat(),
    }
    if days is not None and days > 0 and plan_key != "free":
        expires = now + timedelta(days=days)
        entry["expires_at"] = expires.isoformat()
        entry["duration_days"] = days
    try:
        data = _load_json(PLAN_DATA_FILE)
        data[str(user_id)] = entry
        _save_json(PLAN_DATA_FILE, data)
        log.info(f"✅ Plan '{plan_key}' asignado a user {user_id}")
    except Exception as e:
        log.error(f"Error asignando plan user={user_id}: {e}")
    return entry


def record_admin_audit(actor_id: int, target_id: int, plan_key: str, days: int | None) -> None:
    try:
        data = _load_json(ADMIN_AUDIT_FILE)
        events = data.get("events", [])
        if not isinstance(events, list):
            events = []
        events.insert(0, {
            "at": datetime.now(timezone.utc).isoformat(),
            "actor_id": int(actor_id),
            "target_id": int(target_id),
            "action": "plan_assigned",
            "plan": plan_key,
            "days": days if days and days > 0 else None,
        })
        data["events"] = events[:500]
        _save_json(ADMIN_AUDIT_FILE, data)
    except Exception:
        pass


def admin_report_text() -> str:
    events = _load_json(ADMIN_AUDIT_FILE).get("events", [])
    lines = ["ᴜ́ʟᴛɪᴍᴀꜱ ᴀᴄᴄɪᴏɴᴇꜱ ᴅᴇʟ ᴀᴅᴍɪɴ", ""]
    for event in events[:12]:
        plan = get_plan_info(event.get("plan", "free"))
        duration = event.get("days") or "∞"
        when = str(event.get("at", ""))[:16].replace("T", " ")
        lines.append(f"{plan['badge']} {plan['display']} · {duration} días")
        lines.append(f"ᴜꜱᴜᴀʀɪᴏ: {event.get('target_id', '?')} · {when}")
        lines.append("")
    if not events:
        lines.append("ɴᴏ ʜᴀʏ ᴀᴄᴄɪᴏɴᴇꜱ ɢᴜᴀʀᴅᴀᴅᴀꜱ.")
    return card("🧾 ʀᴇᴘᴏʀᴛᴇ ᴀᴄᴜᴍᴜʟᴀᴛɪᴠᴏ", lines) + f"\n\n{BOT_FOOTER}"


async def broadcast_admin_message(bot_obj, body: str) -> tuple[int, int, int]:
    targets = registered_user_ids()
    sent = failed = 0
    for target_id in targets:
        try:
            await bot_obj.send_message(
                chat_id=target_id,
                text=card("📢 ᴍᴇɴꜱᴀᴊᴇ ᴅᴇʟ ᴀᴅᴍɪɴɪꜱᴛʀᴀᴅᴏʀ", [body]),
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    return len(targets), sent, failed


def get_plan_info(plan_key: str) -> dict:
    return PLANS.get(plan_key, PLANS["free"])


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def quota_period_days(user_id: int) -> int:
    return int(get_plan_info(get_user_plan(user_id)).get("quota_period_days", 1))


def get_daily_usage(user_id: int) -> int:
    if is_owner(user_id):
        return 0
    try:
        data = _load_json(USAGE_DATA_FILE)
        user_data = data.get(str(user_id), {})
        period_start = user_data.get("period_start") if isinstance(user_data, dict) else None
        if period_start:
            try:
                started = datetime.fromisoformat(period_start)
                if datetime.now(timezone.utc) < started + timedelta(days=quota_period_days(user_id)):
                    return int(user_data.get("bytes", 0) or 0)
                return 0
            except Exception:
                pass
        if user_data.get("date") != _today_key():
            return 0
        return user_data.get("bytes", 0)
    except Exception:
        return 0


def add_daily_usage(user_id: int, file_bytes: int) -> None:
    if is_owner(user_id):
        return
    try:
        data = _load_json(USAGE_DATA_FILE)
        today = _today_key()
        user_data = data.get(str(user_id), {})
        period_start = user_data.get("period_start") if isinstance(user_data, dict) else None
        period_active = False
        if period_start:
            try:
                period_active = datetime.now(timezone.utc) < datetime.fromisoformat(period_start) + timedelta(days=quota_period_days(user_id))
            except Exception:
                period_active = False
        if not period_active:
            user_data = {
                "date": today,
                "period_start": datetime.now(timezone.utc).isoformat(),
                "bytes": 0,
                "total_bytes": int(user_data.get("total_bytes", 0) or 0),
            }
        user_data["bytes"] = user_data.get("bytes", 0) + file_bytes
        user_data["total_bytes"] = user_data.get("total_bytes", 0) + file_bytes
        data[str(user_id)] = user_data
        _save_json(USAGE_DATA_FILE, data)
    except Exception as e:
        log.error(f"Error actualizando cuota user={user_id}: {e}")


def get_total_usage(user_id: int) -> int:
    data = _load_json(USAGE_DATA_FILE)
    entry = data.get(str(user_id), {})
    total = entry.get("total_bytes") if isinstance(entry, dict) else 0
    if isinstance(total, (int, float)) and total > 0:
        return int(total)
    return sum(
        int(item.get("size", 0) or 0)
        for item in get_task_history(user_id, 50)
        if isinstance(item, dict)
    )


def _leaderboard_ids() -> list[int]:
    return [uid for uid in registered_user_ids() if get_total_usage(uid) > 0]


def public_leaderboard_text(limit: int = 10) -> str:
    rows = sorted(_leaderboard_ids(), key=get_total_usage, reverse=True)[:limit]
    lines = ["Los usuarios con más GB", "subidos a la nube:", ""]
    if not rows:
        lines.append("Todavía no hay uso registrado.")
    else:
        for position, user_id in enumerate(rows, 1):
            lines.append(f"{position}. Usuario ••••{str(user_id)[-4:]} · {get_total_usage(user_id) / GIB:.2f} GB")
    total = sum(get_total_usage(uid) for uid in _leaderboard_ids())
    lines.extend(["", f"🌐 Total de la comunidad: {total / GIB:.2f} GB"])
    return card("🏆 ᴛᴏᴘ ᴜꜱᴜᴀʀɪᴏꜱ", lines) + f"\n\n{BOT_FOOTER}"


def admin_leaderboard_text(limit: int = 20) -> str:
    users = _load_json(USERS_DATA_FILE).get("users", {})
    rows = sorted(_leaderboard_ids(), key=get_total_usage, reverse=True)[:limit]
    lines = ["Ranking acumulado de archivos", "subidos a ToDus S3:", ""]
    if not rows:
        lines.append("Todavía no hay uso registrado.")
    else:
        for position, user_id in enumerate(rows, 1):
            entry = users.get(str(user_id), {}) if isinstance(users, dict) else {}
            username = entry.get("username") or f"ID {user_id}"
            username = f"@{username.lstrip('@')}" if not username.startswith("ID ") else username
            plan = get_plan_info(get_user_plan(user_id))["display"]
            lines.append(f"{position}. {username}")
            lines.append(f"   ID: {user_id} · {plan} · {get_total_usage(user_id) / GIB:.2f} GB")
    total = sum(get_total_usage(uid) for uid in _leaderboard_ids())
    lines.extend(["", f"🌐 Total acumulado: {total / GIB:.2f} GB"])
    return card("📈 ᴛᴏᴘ ᴅᴇ ᴜꜱᴏ ᴀᴅᴍɪɴ", lines) + f"\n\n{BOT_FOOTER}"


def get_remaining_quota(user_id: int) -> int:
    if is_owner(user_id):
        return 10**18
    plan = get_plan_info(get_user_plan(user_id))
    used = get_daily_usage(user_id)
    return max(0, plan["daily_bytes"] - used)


def next_quota_reset(user_id: int | None = None) -> datetime:
    now = datetime.now(timezone.utc)
    if user_id and quota_period_days(user_id) > 1:
        data = _load_json(USAGE_DATA_FILE).get(str(user_id), {})
        try:
            started = datetime.fromisoformat(data["period_start"])
            reset = started + timedelta(days=quota_period_days(user_id))
            if reset > now:
                return reset
        except Exception:
            pass
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def quota_reset_countdown(user_id: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    tomorrow = next_quota_reset(user_id)
    seconds = max(0, int((tomorrow - now).total_seconds()))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d} (UTC)"


def quota_reset_at_text(user_id: int | None = None) -> str:
    return next_quota_reset(user_id).strftime("%d/%m/%Y a las %H:%M UTC")


async def quota_reset_notifier(application: Application) -> None:
    observed_date = _today_key()
    while True:
        try:
            today = _today_key()
            if today != observed_date:
                data = _load_json(USAGE_DATA_FILE)
                for user_id in registered_user_ids():
                    if quota_period_days(user_id) > 1:
                        continue
                    entry = data.get(str(user_id), {})
                    if not isinstance(entry, dict) or entry.get("date") == today:
                        continue
                    if int(entry.get("bytes", 0) or 0) <= 0:
                        continue
                    if not reset_user_daily_usage(user_id):
                        continue
                    try:
                        await application.bot.send_message(
                            chat_id=user_id,
                            text=card("✅ ᴄᴜᴏᴛᴀ ʀᴇɪɴɪᴄɪᴀᴅᴀ", [
                                "Cuota reiniciada con éxito.",
                                "Ya puedes volver a descargar y subir archivos.",
                                f"⏳ Próximo reinicio: {quota_reset_at_text()}",
                            ]),
                        )
                    except Exception:
                        pass
                observed_date = today
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(30)


# ═══════════════════════════════════════════════════════════════
#  HISTORIAL PERSISTENTE DE TAREAS
# ═══════════════════════════════════════════════════════════════
def save_task_history(user_id: int, task_data: dict) -> None:
    try:
        data = _load_json(HISTORY_DATA_FILE)
        user_history = data.get(str(user_id), [])
        user_history.insert(0, task_data)
        user_history = user_history[:50]
        data[str(user_id)] = user_history
        _save_json(HISTORY_DATA_FILE, data)
    except Exception as e:
        log.error(f"Error guardando historial: {e}")


def get_task_history(user_id: int, limit: int = 10) -> list[dict]:
    try:
        data = _load_json(HISTORY_DATA_FILE)
        return data.get(str(user_id), [])[:limit]
    except Exception:
        return []


def delete_task_history_entry(user_id: int, index: int) -> bool:
    try:
        data = _load_json(HISTORY_DATA_FILE)
        entries = data.get(str(user_id), [])
        if not isinstance(entries, list) or index < 0 or index >= len(entries):
            return False
        entries.pop(index)
        if entries:
            data[str(user_id)] = entries
        else:
            data.pop(str(user_id), None)
        _save_json(HISTORY_DATA_FILE, data)
        return True
    except Exception:
        return False


def clear_task_history(user_id: int) -> bool:
    try:
        data = _load_json(HISTORY_DATA_FILE)
        existed = bool(data.pop(str(user_id), None))
        if existed:
            _save_json(HISTORY_DATA_FILE, data)
        return existed
    except Exception:
        return False


def all_task_history() -> dict[str, list[dict]]:
    data = _load_json(HISTORY_DATA_FILE)
    return data if isinstance(data, dict) else {}


def expire_cloud_files() -> int:
    data = all_task_history()
    now = datetime.now(timezone.utc)
    removed = 0
    changed = False
    for entries in data.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("expires_at"):
                continue
            try:
                exp_dt = datetime.fromisoformat(entry["expires_at"])
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt > now:
                    continue
            except Exception:
                continue
            urls = entry.get("urls", []) if isinstance(entry.get("urls"), list) else []
            success = True
            for url in urls:
                try:
                    delete_from_todus_s3(url)
                except Exception:
                    success = False
            # Purgar caché local del disco al culminar el tiempo del plan
            for cp in entry.get("cached_paths", []):
                try:
                    Path(cp).unlink(missing_ok=True)
                except Exception:
                    pass
            if entry.get("cached_paths"):
                entry["cached_paths"] = []
                changed = True
            if success and urls:
                entry["urls"] = []
                entry["cloud_expired_at"] = now.isoformat()
                removed += len(urls)
                changed = True
    if changed:
        _save_json(HISTORY_DATA_FILE, data)
    return removed


def check_cloud_url_healthy(url: str, timeout: int = 8) -> bool:
    """Verifica si el enlace en ToDus S3 sigue respondiendo activamente."""
    try:
        from todus_s3_storage import check_todus_url_alive
        return check_todus_url_alive(url, timeout_seconds=timeout)
    except Exception:
        return True


async def _silently_update_message_keyboard(
    application: Application,
    chat_id: int | str,
    message_id: int | str,
    task_id: str,
    new_urls: list[str],
) -> None:
    """Actualiza en silencio los botones del mensaje de Telegram con el nuevo enlace renovado."""
    try:
        if not new_urls:
            return
        if len(new_urls) == 1:
            kb = result_keyboard(new_urls[0], task_id)
        else:
            kb = result_multi_keyboard(task_id)
        await application.bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )
    except Exception:
        pass


def renew_prematurely_deleted_cloud_files(application: Application | None = None) -> int:
    """Detecta archivos borrados en ToDus S3 antes de culminar el tiempo del plan
    (ej. plan Free de 12h borrado en ToDus a las 2h) y los vuelve a subir en silencio,
    renovando el archivo y manteniendo el servicio 100% activo sin fallos.
    """
    data = all_task_history()
    now = datetime.now(timezone.utc)
    renewed_count = 0
    changed = False

    for user_id_str, entries in data.items():
        if not isinstance(entries, list):
            continue
        try:
            user_id = int(user_id_str)
        except ValueError:
            continue

        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("expires_at"):
                continue
            try:
                exp_dt = datetime.fromisoformat(entry["expires_at"])
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            # Si ya culminó formalmente el plan, no se renueva
            if exp_dt <= now:
                continue

            urls = entry.get("urls", [])
            cached_paths = entry.get("cached_paths", [])
            if not urls or not cached_paths:
                continue

            # Comprobar si ToDus borró el enlace antes de tiempo
            needs_renewal = False
            for url in urls:
                if not check_cloud_url_healthy(url):
                    needs_renewal = True
                    break

            if needs_renewal:
                log.info(
                    "🛡️ Cloud Guardian: Archivo '%s' (user %s) borrado antes de tiempo en ToDus. Re-subiendo en silencio...",
                    entry.get("filename"), user_id,
                )
                new_urls = []
                renewal_success = True
                for idx, cp_str in enumerate(cached_paths):
                    cp = Path(cp_str)
                    if not cp.is_file() or cp.stat().st_size == 0:
                        renewal_success = False
                        break
                    try:
                        part_fname = entry.get("filename", "file.bin")
                        if len(cached_paths) > 1:
                            part_fname = f"{part_fname}.part{idx+1}"
                        new_url, _ = upload_to_todus_s3(
                            path=cp,
                            download_name=part_fname,
                            telegram_user_id=user_id,
                            timeout_seconds=7200,
                        )
                        new_urls.append(new_url)
                    except Exception as err:
                        log.warning("Fallo al re-subir silenciosamente a ToDus: %s", err)
                        renewal_success = False
                        break

                if renewal_success and new_urls:
                    entry["urls"] = new_urls
                    entry["silently_renewed_at"] = now.isoformat()
                    renewed_count += 1
                    changed = True
                    log.info("✅ Cloud Guardian: Archivo renovado con éxito para usuario %s. Nuevos URLs: %s", user_id, new_urls)
                    if application and entry.get("chat_id") and entry.get("message_id"):
                        asyncio.create_task(
                            _silently_update_message_keyboard(
                                application,
                                entry["chat_id"],
                                entry["message_id"],
                                entry.get("task_id", ""),
                                new_urls,
                            )
                        )

    if changed:
        _save_json(HISTORY_DATA_FILE, data)
    return renewed_count


async def delete_history_entry_cloud(entry: dict) -> bool:
    urls = entry.get("urls", []) if isinstance(entry, dict) else []
    urls = urls if isinstance(urls, list) else []
    for cp in entry.get("cached_paths", []):
        try:
            Path(cp).unlink(missing_ok=True)
        except Exception:
            pass
    entry["cached_paths"] = []
    if not urls:
        return True
    results = await asyncio.gather(*(
        asyncio.to_thread(delete_from_todus_s3, url) for url in urls
    ), return_exceptions=True)
    return True


async def cloud_expiration_monitor(application: Application) -> None:
    while True:
        try:
            # 1. Renueva archivos que ToDus S3 haya borrado antes de finalizar el conteo del plan
            renewed = await asyncio.to_thread(renew_prematurely_deleted_cloud_files, application)
            if renewed:
                log.info("🛡️ Cloud Guardian: %d archivos auto-renovados en silencio.", renewed)

            # 2. Expira y limpia archivos cuyo plan sí culminó formalmente
            removed = await asyncio.to_thread(expire_cloud_files)
            if removed or renewed:
                schedule_data_backup(application, "mantenimiento y auto-renovación de enlaces")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Error en monitor Cloud Guardian: %s", exc)
        await asyncio.sleep(60)


def clear_all_task_history() -> int:
    try:
        data = _load_json(HISTORY_DATA_FILE)
        affected = len(data)
        _save_json(HISTORY_DATA_FILE, {})
        return affected
    except Exception:
        return 0


def reset_user_daily_usage(user_id: int) -> bool:
    try:
        data = _load_json(USAGE_DATA_FILE)
        entry = data.get(str(user_id), {})
        if not isinstance(entry, dict):
            entry = {}
        entry.update({"date": _today_key(), "bytes": 0})
        entry.setdefault("total_bytes", 0)
        data[str(user_id)] = entry
        _save_json(USAGE_DATA_FILE, data)
        return True
    except Exception:
        return False


def quota_exhausted_text() -> str:
    lines = [
        "🚫 Se ha agotado tu",
        "cuota diaria.",
        "",
        "💳 Para seguir debes",
        "comprar un plan o esperar a que se reinicie tu cuota q:",
        "",
        "⭐ VIP Básico: 250$",
        "   📦 10 GB / día",
        "",
        "💎 VIP Medio: 500$",
        "   📦 15 GB / día",
        "",
        "👑 Premium: 1000$",
        "   📦 Ilimitado / día",
        "",
        "🛒 Comprar plan o esperar",
        "a mañana la restauración.",
        f"Para comprar, escribe a @{PLAN_ADMIN_USERNAME}.",
    ]
    box = card("⚠️ ᴄᴜᴏᴛᴀ ᴀɢᴏᴛᴀᴅᴀ", lines)
    return f"{box}\n\n{BOT_FOOTER}"


def quota_exhausted_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("🛒 ᴄᴏᴍᴘʀᴀʀ ᴜɴ ᴘʟᴀɴ", callback_data="plans:buy")],
        [InlineKeyboardButton(sc("🏠 ɪɴɪᴄɪᴏ"), callback_data="home")],
    ])


def check_quota(user_id: int, file_size: int) -> tuple[bool, str]:
    if is_owner(user_id):
        return True, ""
    try:
        plan_key = get_user_plan(user_id)
        plan = get_plan_info(plan_key)
        used = get_daily_usage(user_id)
        remaining = plan["daily_bytes"] - used
        if file_size > remaining:
            return False, quota_exhausted_text()
        return True, ""
    except Exception:
        return True, ""


def quota_lines(user_id: int) -> list[str]:
    if is_owner(user_id):
        return [
            "🏷 Plan: 🜲 Plan Creador",
            "📊 ▓▓▓▓▓▓▓▓▓▓▓▓ ∞%",
            "📦 Usado: 0.00 GB",
            "💾 Libre: ∞ GB",
            "⏳ Duración: Permanente",
        ]
    plan = get_plan_info(get_user_plan(user_id))
    used = get_daily_usage(user_id)
    remaining = max(0, plan["daily_bytes"] - used)
    percent = min(100, int(used * 100 / plan["daily_bytes"])) if plan["daily_bytes"] > 0 else 0
    width = 12
    filled = round(width * percent / 100)
    bar = "▓" * filled + "░" * (width - filled)
    lines = [
        f"🏷 Plan: {plan['badge']} {plan['display']}",
        f"📊 {bar} {percent}%",
        f"📦 Gastado hoy: {used / GIB:.2f} GB",
        f"💾 Libre: {remaining / GIB:.2f} GB",
        f"🔄 Se reinicia en: {quota_reset_countdown(user_id)}",
        f"🕛 Próximo reinicio: {quota_reset_at_text(user_id)}",
    ]
    if plan["rank"] > 0 and plan["rank"] != 999:
        exp_date, rem_days = get_plan_expiry_info(user_id)
        if exp_date:
            lines.append(f"📅 Vence: {exp_date}")
        if rem_days is not None:
            lines.append(f"⏳ Restan: {rem_days} días")
    return lines


# ═══════════════════════════════════════════════════════════════
#  GESTOR DE COLA FAIR TASK QUEUE
# ═══════════════════════════════════════════════════════════════
import uuid
from collections import defaultdict, deque

class TransferTask:
    def __init__(self, user_id, chat_id, source_kind, source_message=None, status_message=None, source_url=None, username=None, display_name=None):
        self.task_id = uuid.uuid4().hex[:10]
        self.user_id = user_id
        self.chat_id = chat_id
        self.source_kind = source_kind
        self.source_message = source_message
        self.status_message = status_message
        self.source_url = source_url
        self.username = username
        self.display_name = display_name
        self.filename = None
        self.size = 0
        self.temp_path = None
        self.download_complete = False
        self.part_paths = []
        self.part_urls = {}
        self.state = "queued"
        self.error = None
        self.cancel_requested = False
        self.txt_generating = False
        self.created_at = time.time()
        self.updated_at = time.time()
    def set_state(self, state: str) -> None:
        self.state = state
        self.updated_at = time.time()
    def is_active(self) -> bool:
        return self.state in {"downloading", "uploading"}

class FairTaskQueue:
    """Gestor de colas 100% INDEPENDIENTES por cada usuario con balanceo equitativo (Fair-Share).
    Cada usuario tiene su propio hilo/cola de ejecución: los archivos de un usuario jamás
    retrasan, bloquean ni ponen en espera a otro usuario.
    Las películas o APKs pausadas NO cuentan como cola activa."""
    def __init__(self, max_concurrent_per_user=2):
        self.jobs = {}
        self.user_queues = defaultdict(deque)
        self.user_active = defaultdict(set)
        self.default_concurrent_per_user = max_concurrent_per_user
        self._lock = asyncio.Lock()
        self._notify_event = asyncio.Event()

    def get_user_concurrency(self, user_id: int) -> int:
        if is_owner(user_id):
            return 4
        plan_key = get_user_plan(user_id)
        if plan_key == "premium":
            return 3
        elif plan_key in {"vip_medium", "vip_basic"}:
            return 2
        return 1

    async def enqueue(self, job, user_limit=25):
        async with self._lock:
            # Solo cuentan como pendientes las tareas activas o en cola; las PAUSADAS NO ocupan cupo
            active_or_queued = sum(
                1 for j in self.jobs.values()
                if j.user_id == job.user_id and j.state in {"queued", "downloading", "uploading"}
            )
            if active_or_queued >= user_limit:
                return False
            self.jobs[job.task_id] = job
            self.user_queues[job.user_id].append(job)
            self._notify_event.set()
            return True

    async def take(self):
        """Selecciona la siguiente tarea de forma equitativa por usuario, garantizando que
        cada usuario tenga su propia cola de ejecución independiente sin interferencias."""
        while True:
            async with self._lock:
                for uid, q in list(self.user_queues.items()):
                    if not q:
                        continue
                    max_allowed = self.get_user_concurrency(uid)
                    if len(self.user_active[uid]) < max_allowed:
                        while q:
                            candidate = q.popleft()
                            if candidate.state in {"paused", "cancelled", "done", "error"}:
                                continue
                            self.user_active[uid].add(candidate.task_id)
                            return candidate
                self._notify_event.clear()
            await self._notify_event.wait()

    def task_finished(self, job):
        if not job:
            return
        if job.user_id in self.user_active:
            self.user_active[job.user_id].discard(job.task_id)
        self._notify_event.set()

    async def cancel(self, task_id, user_id):
        async with self._lock:
            job = self.jobs.get(task_id)
            if not job or job.user_id != user_id:
                return False
            job.cancel_requested = True
            if job.state == "queued":
                job.set_state("paused")
                self.user_queues[user_id] = deque(j for j in self.user_queues[user_id] if j.task_id != task_id)
            self.task_finished(job)
            return True

    async def requeue(self, job):
        async with self._lock:
            job.cancel_requested = False
            job.error = None
            job.set_state("queued")
            if job not in self.user_queues[job.user_id]:
                self.user_queues[job.user_id].append(job)
            self._notify_event.set()
            return True

    async def delete(self, task_id, user_id):
        async with self._lock:
            job = self.jobs.get(task_id)
            if not job or job.user_id != user_id or job.is_active():
                return None
            self.jobs.pop(task_id, None)
            if user_id in self.user_queues:
                self.user_queues[user_id] = deque(j for j in self.user_queues[user_id] if j.task_id != task_id)
            self.task_finished(job)
            return job

    def for_user(self, user_id, states=None):
        return sorted(
            [j for j in self.jobs.values() if j.user_id == user_id and (states is None or j.state in states)],
            key=lambda j: j.created_at,
            reverse=True
        )

    def get_local_active(self, user_id):
        return [j for j in self.jobs.values() if j.user_id == user_id and j.is_active()]

    def get_local_queued(self, user_id):
        return [j for j in self.jobs.values() if j.user_id == user_id and j.state == "queued"]

    def get_local_paused(self, user_id):
        return [j for j in self.jobs.values() if j.user_id == user_id and j.state in {"paused", "error"}]

    def get_global_active_count(self):
        return sum(1 for j in self.jobs.values() if j.is_active())

    def get_global_active_users_count(self):
        return len({j.user_id for j in self.jobs.values() if j.is_active()})

    def get_global_queued_count(self):
        return sum(1 for j in self.jobs.values() if j.state == "queued")

# ═══════════════════════════════════════════════════════════════
#  INTEGRACIÓN CON TODUS S3 CUBA
# ═══════════════════════════════════════════════════════════════
class _ToDusProgressStream:
    def __init__(self, file_obj, total: int, *, on_progress=None, is_cancelled=None, deadline: float):
        self._file = file_obj
        self._total = total
        self._sent = 0
        self._on_progress = on_progress
        self._is_cancelled = is_cancelled
        self._deadline = deadline
    def __len__(self) -> int:
        return max(0, self._total - self._sent)
    def _check(self) -> None:
        if self._is_cancelled and self._is_cancelled():
            raise RuntimeError("Subida cancelada.")
        if time.monotonic() > self._deadline:
            raise RuntimeError("Se agotó el tiempo máximo de subida a ToDus S3.")
    def read(self, size: int = -1) -> bytes:
        self._check()
        chunk = self._file.read(64 * 1024 if size is None or size < 0 else size)
        if chunk:
            self._sent += len(chunk)
            if self._on_progress:
                try:
                    self._on_progress(self._sent, self._total)
                except Exception:
                    pass
        return chunk
    def __iter__(self):
        while True:
            chunk = self.read(64 * 1024)
            if not chunk:
                break
            yield chunk
    def __getattr__(self, name):
        return getattr(self._file, name)

def _build_todus_object_key(telegram_user_id: int, filename: str) -> str:
    import uuid
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    folder_id = uuid.uuid4().hex[:6]
    file_id = uuid.uuid4().hex[:12]
    original_name = Path(filename or "download.bin").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._") or "download.bin"
    extension = Path(safe_name).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,16}", extension):
        extension = ".bin"
        safe_name = f"{Path(safe_name).stem or 'download'}{extension}"
    return f"users/tg_{int(telegram_user_id)}/telegram/{stamp}-{folder_id}/telegram_{file_id}_{safe_name}"

def upload_to_todus_s3(path: Path, download_name: str, telegram_user_id: int, on_progress=None, timeout_seconds=86400, is_cancelled=None):
    try:
        from todus_s3_storage import upload_to_todus_s3 as _real_storage_upload
        return _real_storage_upload(
            local_path=path,
            filename=download_name,
            telegram_user_id=telegram_user_id,
            on_progress=on_progress,
            timeout_seconds=timeout_seconds,
            is_cancelled=is_cancelled,
            base_url=TODUS_BASE_URL,
        )
    except Exception as exc:
        log.info("Usando uploader HTTP directo a ToDus S3: %s", exc)

    import requests
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {file_path}")
    size = file_path.stat().st_size
    key = _build_todus_object_key(telegram_user_id, download_name)
    url = f"{TODUS_BASE_URL.rstrip('/')}/{quote(key, safe='/')}"
    content_type = mimetypes.guess_type(download_name)[0] or "application/octet-stream"
    encoded_name = quote(download_name, safe="")
    ascii_name = "".join(c if 32 <= ord(c) < 127 and c not in {'"', "\\", ";"} else "_" for c in download_name).strip() or "download.bin"
    disposition = "attachment" if Path(download_name).suffix.lower() == ".apk" else "inline"
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(size),
        "Content-Disposition": f'{disposition}; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}',
        "User-Agent": "Wget/1.21.3",
        "Host": "s3.todus.cu",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    timeout = max(30, int(timeout_seconds))
    deadline = time.monotonic() + timeout
    with requests.Session() as session:
        for attempt in range(3):
            if is_cancelled and is_cancelled():
                raise RuntimeError("Subida cancelada.")
            target_urls = [url]
            if "s3.todus.cu" in url:
                target_urls.append(url.replace("s3.todus.cu", "152.207.206.86"))
            for target_url in target_urls:
                verify_ssl = not ("152.207.206.86" in target_url)
                try:
                    with file_path.open("rb") as f_obj:
                        body = _ToDusProgressStream(
                            f_obj, size, on_progress=on_progress, is_cancelled=is_cancelled, deadline=deadline
                        )
                        resp = session.put(target_url, data=body, headers=headers, timeout=(30, timeout), verify=verify_ssl)
                        if resp.status_code in {200, 201, 204}:
                            return url, size
                        if resp.status_code >= 500 and attempt < 2:
                            continue
                except requests.RequestException:
                    continue
            if attempt < 2 and time.monotonic() < deadline:
                time.sleep(2)
                continue
    raise RuntimeError("No se pudo completar la subida a ToDus S3.")

def delete_from_todus_s3(url: str) -> bool:
    try:
        from todus_s3_storage import delete_from_todus_s3 as _real_storage_delete
        _real_storage_delete(url, base_url=TODUS_BASE_URL)
        return True
    except Exception:
        pass
    try:
        import requests
        headers = {"User-Agent": "JK-Telegram-Bot/2.8"}
        resp = requests.delete(url, timeout=30, headers=headers)
        return resp.status_code in {200, 204, 404}
    except Exception as exc:
        log.warning(f"Error borrando de ToDus S3: {exc}")
        return False


# ═══════════════════════════════════════════════════════════════
#  UTILIDADES DE RED Y ARCHIVOS
# ═══════════════════════════════════════════════════════════════
def extract_http_urls(text: str) -> list[str]:
    matches = re.findall(r"https?://[^\s<>]+", text, flags=re.IGNORECASE)
    if not matches:
        raise ValueError("Pega uno o varios enlaces directos")
    urls = [validate_url_syntax(c.rstrip(".,;:!?)]}")) for c in matches]
    if len(urls) > 20:
        raise ValueError("Máximo 20 enlaces por mensaje")
    return urls


def validate_url_syntax(raw: str) -> str:
    raw = raw.strip()
    if not raw or len(raw) > URL_MAX_CHARS or any(ord(c) < 32 for c in raw):
        raise ValueError("URL inválida")
    try:
        parts = urlsplit(raw)
        parts.port
    except ValueError as exc:
        raise ValueError("URL mal formada") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Solo HTTP o HTTPS")
    if not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError("Host inválido")
    host = parts.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Hosts locales no permitidos")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("Dominio inválido")
    else:
        if not address.is_global:
            raise ValueError("IPs privadas no permitidas")
    return raw


class PublicOnlyResolver(AbstractResolver):
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_UNSPEC):
        loop = asyncio.get_running_loop()
        try:
            direct_ip = ipaddress.ip_address(host.split("%", 1)[0])
            addresses = [(direct_ip, socket.AF_INET6 if direct_ip.version == 6 else socket.AF_INET)]
        except ValueError:
            infos = await loop.getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
            addresses, seen = [], set()
            for info in infos:
                ip = ipaddress.ip_address(info[4][0].split("%", 1)[0])
                if ip.compressed not in seen:
                    seen.add(ip.compressed)
                    addresses.append((ip, info[0]))
        if not addresses:
            raise OSError("No resolvió")
        result = []
        for ip, fam in addresses:
            if not ip.is_global:
                raise OSError("IP privada")
            result.append({"hostname": host, "host": ip.compressed, "port": port, "family": fam, "proto": 0, "flags": 0})
        return result

    async def close(self) -> None:
        return None


def clean_filename(name: str | None, fallback: str = "download.bin") -> str:
    if name:
        name = name.replace("\\", "/").split("/")[-1]
        name = "".join(ch for ch in name if ch.isprintable() and ch not in "\r\n\0")
        name = name.strip(" .")[:160]
    if not name:
        name = fallback
    return re.sub(r'[<>:"|?*]', "_", name) or fallback


def is_private_update(update: Update) -> bool:
    chat = getattr(update, "effective_chat", None)
    return chat is None or chat.type == "private"


def normalize_telegram_generated_name(name: str | None, fallback: str) -> str:
    cleaned = clean_filename(name, fallback)
    stripped = re.sub(r"^(?:telegram|tg)[_-]+", "", cleaned, flags=re.IGNORECASE)
    return clean_filename(stripped, fallback)


def filename_from_response(headers, final_url: str) -> str:
    disposition = headers.get("Content-Disposition") if hasattr(headers, "get") else None
    filename = None
    if disposition:
        msg = Message()
        msg["content-disposition"] = disposition
        candidate = msg.get_filename()
        if candidate:
            filename = clean_filename(candidate)
    if not filename:
        path_name = urlsplit(final_url).path.rsplit("/", 1)[-1]
        filename = clean_filename(path_name, "download")
    if not Path(filename).suffix:
        content_type = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        extension = mimetypes.guess_extension(content_type) if content_type else None
        if content_type == "application/vnd.android.package-archive":
            extension = ".apk"
        if extension and re.fullmatch(r"\.[a-zA-Z0-9]{1,16}", extension):
            filename += extension.lower()
        else:
            filename += ".bin"
    return filename


def validate_downloaded_file(path: Path, filename: str) -> None:
    if Path(filename).suffix.lower() != ".apk":
        return
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            if (
                package.testzip() is not None
                or "AndroidManifest.xml" not in names
                or "classes.dex" not in names
            ):
                raise ValueError
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        raise ValueError(
            "El archivo .apk no es válido o está dañado; se rechazó antes de subirlo."
        ) from exc


class DownloadPaused(RuntimeError):
    def __init__(self, path: Path):
        super().__init__("Descarga pausada")
        self.path = path


def normalize_apk_filename(path: Path, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
            split_members = [name for name in names if name.lower().endswith(".apk")]
            if (
                "base.apk" in names
                or len(split_members) > 0
                or suffix in {".xapk", ".apks"}
            ):
                raise ValueError(
                    "El enlace contiene un paquete dividido (XAPK/APKS), no un APK único instalable."
                )
            is_apk = (
                "AndroidManifest.xml" in names
                and "classes.dex" in names
                and package.testzip() is None
            )
    except zipfile.BadZipFile:
        is_apk = False
    if is_apk and suffix != ".apk":
        stem = Path(filename).stem or "application"
        return clean_filename(f"{stem}.apk", "application.apk")
    return filename


async def download_to_temp(session, original_url, progress_callback=None, max_bytes=None,
                           is_cancelled=None, partial_path: Path | None = None):
    url = validate_url_syntax(original_url)
    if "play.google.com/store/apps" in url.lower():
        raise ValueError("Ese enlace es una ficha de Google Play, no un APK directo.")
    if partial_path is None:
        tmp = tempfile.NamedTemporaryFile(prefix="tg-download-", suffix=".part", dir=TMPDIR, delete=False)
        path = Path(tmp.name)
        tmp.close()
    else:
        path = Path(partial_path)
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        for redirect_count in range(MAX_REDIRECTS + 1):
            validate_url_syntax(url)
            existing = path.stat().st_size if path.exists() else 0
            request_headers = {"Range": f"bytes={existing}-"} if existing else {}
            async with session.get(url, allow_redirects=False, headers=request_headers) as response:
                if response.status in REDIRECT_STATUSES:
                    location = response.headers.get("Location")
                    if not location or redirect_count == MAX_REDIRECTS:
                        raise ValueError("Demasiadas redirecciones")
                    url = validate_url_syntax(urljoin(url, location))
                    continue
                if response.status < 200 or response.status >= 300:
                    raise ValueError(f"HTTP {response.status}")
                content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                path_suffix = Path(urlsplit(str(response.url)).path).suffix.lower()
                if content_type in {"text/html", "application/xhtml+xml"} and path_suffix not in {".html", ".htm"}:
                    raise ValueError("El enlace devolvió una página web, no un archivo directo.")
                if max_bytes and response.content_length and response.content_length > max_bytes:
                    raise ValueError(f"Supera {_size_label(max_bytes, 0)}")
                if existing and response.status == 206:
                    total = existing
                    content_length = existing + (response.content_length or 0)
                    file_mode = "ab"
                else:
                    total = 0
                    content_length = response.content_length or 0
                    file_mode = "wb"
                with path.open(file_mode, buffering=16 * 1024 * 1024) as output:
                    async for chunk in response.content.iter_chunked(16 * 1024 * 1024):
                        if is_cancelled and is_cancelled():
                            raise DownloadPaused(path)
                        total += len(chunk)
                        if max_bytes and total > max_bytes:
                            raise ValueError(f"Supera {_size_label(max_bytes, 0)}")
                        output.write(chunk)
                        if progress_callback:
                            await progress_callback(total, content_length)
                if total == 0:
                    raise ValueError("Archivo vacío")
                filename = filename_from_response(response.headers, str(response.url))
                filename = normalize_apk_filename(path, filename)
                return path, filename, total
        raise ValueError("No se pudo seguir el enlace")
    except DownloadPaused:
        raise
    except Exception:
        path.unlink(missing_ok=True)
        raise


async def download_telegram_media(message, mtproto_client=None, progress_callback=None,
                                   local_bot_api=False, mtproto_message_cache=None):
    media, filename, fallback = None, None, "telegram_file.bin"
    if message.document:
        media, filename = message.document, message.document.file_name
        if not filename:
            mime_type = (getattr(media, "mime_type", "") or "").split(";", 1)[0].lower()
            if mime_type == "application/vnd.android.package-archive":
                filename = "application.apk"
            elif mime_type:
                filename = f"telegram{mimetypes.guess_extension(mime_type) or '.bin'}"
    elif message.video:
        media, filename, fallback = message.video, message.video.file_name, "video.mp4"
    elif message.animation:
        media, filename, fallback = message.animation, message.animation.file_name, "animation.mp4"
    elif message.audio:
        media, filename, fallback = message.audio, message.audio.file_name, "audio.mp3"
    elif message.voice:
        media, fallback = message.voice, "voice.ogg"
    elif message.video_note:
        media, fallback = message.video_note, "video_note.mp4"
    elif message.photo:
        media, fallback = message.photo[-1], "photo.jpg"
    if media is None:
        raise ValueError("No encontré archivo compatible")
    tmp = tempfile.NamedTemporaryFile(prefix="tg-forward-", suffix=".part", dir=TMPDIR, delete=False)
    path = Path(tmp.name)
    tmp.close()
    try:
        size_hint = getattr(media, "file_size", None)
        use_mtproto = mtproto_client is not None and (size_hint is None or size_hint > BOT_API_DOWNLOAD_LIMIT)
        mtproto_downloaded = False

        if use_mtproto and mtproto_client:
            original = None
            cache_key = (message.chat_id, message.message_id)
            if mtproto_message_cache:
                original = mtproto_message_cache.get(cache_key)

            if original is None:
                try:
                    msgs = await mtproto_client.get_messages(message.chat_id, ids=message.message_id)
                    if isinstance(msgs, (list, tuple)) and msgs:
                        original = msgs[0]
                    elif msgs:
                        original = msgs
                except Exception as first_exc:
                    try:
                        chat_peer = await mtproto_client.get_entity(message.chat_id)
                        msgs = await mtproto_client.get_messages(chat_peer, ids=message.message_id)
                        if isinstance(msgs, (list, tuple)) and msgs:
                            original = msgs[0]
                        elif msgs:
                            original = msgs
                    except Exception as exc:
                        log.warning("No se pudo resolver mensaje MTProto por chat_id: %s", exc)

            if original is None or not getattr(original, "media", None):
                fwd_chat = getattr(message, "forward_from_chat", None)
                fwd_id = getattr(message, "forward_from_message_id", None)
                if not fwd_chat and getattr(message, "forward_origin", None):
                    origin = message.forward_origin
                    fwd_chat = getattr(origin, "chat", None)
                    fwd_id = getattr(origin, "message_id", None)
                if fwd_chat and fwd_id:
                    try:
                        target = getattr(fwd_chat, "username", None) or fwd_chat.id
                        ch_entity = await mtproto_client.get_entity(target)
                        msgs = await mtproto_client.get_messages(ch_entity, ids=fwd_id)
                        if isinstance(msgs, (list, tuple)) and msgs:
                            original = msgs[0]
                        elif msgs:
                            original = msgs
                    except Exception as exc:
                        log.warning("No se pudo resolver reenvío en canal MTProto: %s", exc)

            if original and getattr(original, "media", None):
                for attempt in range(3):
                    path.unlink(missing_ok=True)
                    try:
                        res = await mtproto_client.download_media(original, file=str(path), progress_callback=progress_callback)
                        if res and path.exists() and path.stat().st_size > 0:
                            mtproto_downloaded = True
                            break
                    except Exception as exc:
                        log.warning("Descarga MTProto intento %d falló: %s", attempt + 1, exc)
                        await asyncio.sleep(1.5)

        if not mtproto_downloaded:
            if size_hint and size_hint > BOT_API_DOWNLOAD_LIMIT:
                raise ValueError(
                    "Archivo muy grande para la Bot API de Telegram (más de 20 MiB). "
                    "Configura TELEGRAM_API_ID y TELEGRAM_API_HASH para descargarlo con MTProto."
                )
            for attempt in range(3):
                path.unlink(missing_ok=True)
                try:
                    try:
                        telegram_file = await media.get_file(read_timeout=240, connect_timeout=45)
                    except TypeError:
                        telegram_file = await media.get_file()
                    await telegram_file.download_to_drive(custom_path=str(path))
                    if path.exists() and path.stat().st_size > 0:
                        break
                except (TimedOut, TimeoutError, asyncio.TimeoutError, aiohttp.ClientError):
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
                except Exception as exc:
                    if attempt == 2:
                        raise ValueError(f"No se pudo descargar el archivo de Telegram ({exc})")
                    await asyncio.sleep(1.5)

        actual_size = path.stat().st_size
        if actual_size == 0:
            raise ValueError("El archivo recibido está vacío.")
        safe_filename = normalize_telegram_generated_name(filename, fallback)
        safe_filename = normalize_apk_filename(path, safe_filename)
        validate_downloaded_file(path, safe_filename)
        return path, safe_filename, actual_size
    except Exception:
        path.unlink(missing_ok=True)
        raise


def _duration_label(seconds: float | None) -> str:
    if seconds is None:
        return "calculando"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def format_media_header(filename: str = "", source_url: str | None = None) -> str:
    name = (filename or "").strip()
    if not name and source_url:
        low = source_url.lower()
        if "youtube.com" in low or "youtu.be" in low:
            name = "Video de YouTube.mp4"
        elif "tiktok.com" in low:
            name = "Video de TikTok.mp4"
        elif "facebook.com" in low or "fb.watch" in low:
            name = "Video de Facebook.mp4"
        elif "instagram.com" in low:
            name = "Video de Instagram.mp4"
        else:
            try:
                name = Path(urlsplit(source_url).path).name or "Archivo.bin"
            except Exception:
                name = "Archivo.bin"
    if not name:
        name = "Archivo"

    ext = Path(name).suffix.lower()
    stem = Path(name).stem if ext else name
    display_title = stem[:34] + (ext if ext else "")

    if ext in {".mp4", ".mkv", ".avi", ".mov", ".flv", ".webm", ".ts", ".3gp", ".m4v"} or (source_url and any(h in source_url.lower() for h in ("youtube", "youtu.be", "tiktok", "facebook", "fb.watch"))):
        icon = "🎬"
    elif ext in {".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac", ".opus"}:
        icon = "🎵"
    elif ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
        icon = "🖼️"
    elif ext in {".apk", ".xapk"}:
        icon = "📱"
    elif ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        icon = "📦"
    elif ext in {".pdf", ".docx", ".doc", ".xlsx", ".txt"}:
        icon = "📑"
    else:
        icon = "📄"

    return f"{icon} <b>{display_title}</b>"


def _size_label(size: int | float, decimals: int = 2) -> str:
    size = max(0, float(size))
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.{decimals}f} GB"
    return f"{size / 1_000_000:.{decimals}f} MB"


def upload_progress_text(sent: int, total: int, speed: float = 0, eta: float | None = None, filename: str = "", source_url: str | None = None) -> str:
    percent = 100.0 if total <= 0 else min(100.0, (sent * 100.0 / total))
    width = 15
    filled = round(width * (percent / 100.0))
    bar = "⬢" * filled + "⬡" * (width - filled)
    header = format_media_header(filename, source_url)
    eta_str = f"{int(eta)}s" if (eta is not None and eta > 0) else "Calculando..."
    sent_mb = f"{sent / (1024 * 1024):.1f} MB"
    total_mb = f"{total / (1024 * 1024):.1f} MB" if total > 0 else "Desconocido"
    speed_mb = f"{max(0.1, speed):.1f} MB/s" if speed > 0 else "0.0 MB/s"

    out = [
        "┎ 📤 <b>ѕᴜʙɪᴇɴᴅᴏ ᴀ ᴛᴏᴅᴜѕ ѕ3</b>",
        "┠──────────────────────",
    ]
    if header:
        out.append(f"┠ {header}")
    out.extend([
        "┃",
        f"┠ |{bar}|",
        f"┠ ᴘᴏʀᴄᴇɴᴛᴀᴊᴇ: {percent:.2f}%",
        f"┠ ᴘʀᴏᴄᴇѕᴀᴅᴏ: {sent_mb}/{total_mb}",
        f"┠ ᴠᴇʟᴏᴄɪᴅᴀᴅ ᴅᴇ ѕᴜʙɪᴅᴀ: {speed_mb}",
        f"┖ ᴇᴛᴀ: {eta_str}",
    ])
    return "\n".join(out)


def download_progress_text(received: int, total: int, speed: float = 0, eta: float | None = None, filename: str = "", source_url: str | None = None) -> str:
    percent = 100.0 if total <= 0 else min(100.0, (received * 100.0 / total))
    width = 15
    filled = round(width * (percent / 100.0))
    bar = "⬢" * filled + "⬡" * (width - filled)
    header = format_media_header(filename, source_url)
    eta_str = f"{int(eta)}s" if (eta is not None and eta > 0) else "Calculando..."
    rec_mb = f"{received / (1024 * 1024):.1f} MB"
    total_mb = f"{total / (1024 * 1024):.1f} MB" if total > 0 else "Desconocido"
    speed_mb = f"{max(0.1, speed):.1f} MB/s" if speed > 0 else "0.0 MB/s"

    out = [
        "┎ 📥 <b>ᴅᴇѕᴄᴀʀɢᴀɴᴅᴏ ʀᴇᴄᴜʀѕᴏ</b>",
        "┠──────────────────────",
    ]
    if header:
        out.append(f"┠ {header}")
    out.extend([
        "┃",
        f"┠ |{bar}|",
        f"┠ ᴘᴏʀᴄᴇɴᴛᴀᴊᴇ: {percent:.2f}%",
        f"┠ ᴘʀᴏᴄᴇѕᴀᴅᴏ: {rec_mb}/{total_mb}",
        f"┠ ᴠᴇʟᴏᴄɪᴅᴀᴅ ᴅᴇ ᴅᴇѕᴄᴀʀɢᴀ: {speed_mb}",
        f"┖ ᴇᴛᴀ: {eta_str}",
    ])
    return "\n".join(out)


async def upload_to_todus_s3_with_progress(
    status, path: Path, download_name: str, telegram_user_id: int,
    reply_markup=None, is_cancelled=None,
) -> tuple[str, int]:
    loop = asyncio.get_running_loop()
    state = {"last_time": 0.0, "last_bucket": -1, "last_sent": 0, "start_time": time.monotonic()}

    async def edit_progress(sent, total, speed, eta):
        try:
            await status.edit_text(
                upload_progress_text(sent, total, speed, eta, filename=download_name),
                reply_markup=reply_markup() if callable(reply_markup) else reply_markup,
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    try:
        initial_total = path.stat().st_size
    except OSError:
        initial_total = 0
    if initial_total:
        await edit_progress(0, initial_total, 0, None)

    def on_progress(sent, total):
        percent = 100 if total <= 0 else min(100, int(sent * 100 / total))
        now = time.monotonic()
        if sent < state["last_sent"]:
            state["last_time"], state["last_bucket"], state["start_time"] = 0.0, -1, now
        state["last_sent"] = sent
        bucket = percent // 5
        if percent < 100 and (bucket <= state["last_bucket"] or now - state["last_time"] < 1.5):
            return
        state["last_time"], state["last_bucket"] = now, bucket
        elapsed = max(0.1, now - state["start_time"])
        speed = sent / MIB / elapsed
        eta = (total - sent) / (speed * MIB) if speed > 0 else None
        try:
            asyncio.run_coroutine_threadsafe(edit_progress(sent, total, speed, eta), loop)
        except Exception:
            pass

    return await asyncio.to_thread(
        upload_to_todus_s3, path, download_name, telegram_user_id,
        on_progress=on_progress,
        timeout_seconds=MAX_TRANSFER_HOURS * 3600,
        is_cancelled=is_cancelled,
    )


def _part_filename(filename: str, index: int, total: int) -> str:
    if total == 1:
        return filename
    path = Path(filename)
    return f"{path.stem}.part{index:03d}{path.suffix}"


def link_txt_filename(filename: str | None) -> str:
    stem = Path(filename or "archivo").stem
    return f"{clean_filename(stem, 'archivo')}.txt"


def split_into_parts(source: Path, filename: str, work_dir: Path, part_size: int) -> list[Path]:
    size = source.stat().st_size
    if size <= part_size:
        return [source]
    work_dir.mkdir(parents=True, exist_ok=True)
    result = []
    buffer_chunk = 16 * 1024 * 1024
    with source.open("rb", buffering=buffer_chunk) as inp:
        index = 1
        total_parts = (size + part_size - 1) // part_size
        while True:
            target = work_dir / _part_filename(filename, index, total_parts)
            written = 0
            with target.open("wb", buffering=buffer_chunk) as out:
                while written < part_size:
                    chunk = inp.read(min(buffer_chunk, part_size - written))
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
            if not written:
                target.unlink(missing_ok=True)
                break
            result.append(target)
            index += 1
    return result


def btn(text: str, **kwargs) -> InlineKeyboardButton:
    return InlineKeyboardButton(sc(text), **kwargs)


def main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    balance = get_user_balance(user_id) if user_id is not None else 0
    return InlineKeyboardMarkup([
        [btn("📥 DESCARGAS", callback_data="downloads")],
        [btn(f"💸 Saldo: {balance}$ • Referidos", callback_data="balance")],
        [btn("❓ Ayuda", callback_data="help:0"), btn("☁️ Mi Nube", callback_data="open_history")],
        [btn("📋 Cola", callback_data="open_queue"), btn("💬 Soporte", callback_data="support")],
        [btn("📊 Mi cuota", callback_data="my_quota"), btn("🏆 Top usuarios", callback_data="top:users")],
        [btn("📢 ᴊᴋ ᴄʜᴀɴɴᴇʟꫂꤪꤨᴼᶠᶜ", url=CHANNEL_JOIN_URL)],[btn("📢 ᴊᴋ ᴄʜᴀᴛꫂꤪꤨᴼᶠᶜ", url=GROUP_JOIN_URL)],
    ])


def plans_text(user_id: int, bot_username: str | None = None) -> str:
    balance = get_user_balance(user_id)
    link = referral_link(user_id, bot_username)
    lines = [
        f"💸 Saldo disponible: {balance}$",
        "",
        "🎁 Al registrarte recibes 5-10$.",
        "👥 Invita a un amigo o contacto:",
        "Tú recibes 5-10$ y tu amigo",
        "recibe 5-10$ de bienvenida y tú ganas 10$ por cada referido.",
        "",
        "📋 Planes disponibles:",
        "🆓 Gratis · 2 GB/día · 12h nube",
        "⭐ VIP Básico · 10 GB/día · 250$",
        "💎 VIP Medio · 15 GB/día · 500$",
        "👑 Premium · Ilimitado · 1000$",
        "",
        "💡 Copia tu enlace abajo para",
        "compartirlo con tus amigos.",
    ]
    box = card("💸 ꜱᴀʟᴅᴏ ʏ ʀᴇꜰᴇʀɪᴅᴏꜱ", lines)
    return (
        f"{box}\n\n"
        f"🔗 <b>Tu enlace de referido:</b>\n"
        f"<code>{link}</code>\n\n"
        f"{BOT_FOOTER}"
    )


def plans_keyboard(user_id: int, bot_username: str | None = None) -> InlineKeyboardMarkup:
    link = referral_link(user_id, bot_username)
    share_url = "https://t.me/share/url?url=" + quote(link, safe="") + "&text=" + quote(
        "Únete a JK Down Bot y recibe 5$ de bienvenida.", safe=""
    )
    return InlineKeyboardMarkup([
        [btn("🛒 ᴠᴇʀ ᴘʟᴀɴᴇꜱ ʏ ᴄᴏᴍᴘʀᴀʀ", callback_data="plans:buy")],
        [btn("📤 ᴄᴏᴍᴘᴀʀᴛɪʀ ᴇʟ ʙᴏᴛ", url=share_url),
         btn("📋 ᴄᴏᴘɪᴀʀ ᴍɪ ᴇɴʟᴀᴄᴇ", copy_text=CopyTextButton(text=link))],
        [btn("🔄 ᴀᴄᴛᴜᴀʟɪᴢᴀʀ ꜱᴀʟᴅᴏ", callback_data="balance"),
         btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")],
    ])


def plan_purchase_text(user_id: int) -> str:
    balance = get_user_balance(user_id)
    lines = [f"💸 Saldo disponible: {balance}$", "", "Solo puedes confirmar un plan si tienes el saldo completo.", ""]
    for key in ("premium", "vip", "ultra"):
        plan = PLANS[key]
        state = "✅ Disponible" if balance >= plan["price_value"] else f"🔒 Faltan {plan['price_value'] - balance}$"
        lines.extend([
            f"{plan['badge']} {plan['display']} · {plan['price']}",
            f"📦 {plan['daily_label']}/día · enlace {plan['storage_label']}",
            state,
            "",
        ])
    lines.append("Al confirmar, se descuenta el precio y se activa el plan automáticamente.")
    return f"{card('🛒 ᴘʟᴀɴᴇꜱ ᴘᴀʀᴀ ᴄᴏᴍᴘʀᴀʀ', lines)}\n\n{BOT_FOOTER}"


def plan_purchase_keyboard(user_id: int) -> InlineKeyboardMarkup:
    balance = get_user_balance(user_id)
    rows = []
    for key in ("premium", "vip", "ultra"):
        plan = PLANS[key]
        if balance >= plan["price_value"]:
            rows.append([btn(f"✅ {plan['display']} · {plan['price']}", callback_data=f"plans:confirm:{key}")])
        else:
            rows.append([btn(f"🔒 {plan['display']} · {plan['price']}", callback_data=f"plans:unavailable:{key}")])
    rows.extend([
        [btn("⬅️ ᴠᴏʟᴠᴇʀ ᴀ ᴘʟᴀɴᴇꜱ", callback_data="plans")],
        [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")],
    ])
    return InlineKeyboardMarkup(rows)


def download_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("📁 Telegram", callback_data="download:telegram"),
         btn("🔗 Enlace", callback_data="download:url")],
        [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")],
    ])


def download_menu_text() -> str:
    return card("📥 ᴄᴇɴᴛʀᴏ ᴅᴇ ᴅᴇꜱᴄᴀʀɢᴀꜱ", [
        "Elige el método.",
        "",
        "📁 Telegram: documento,",
        "video, audio o foto.",
        "",
        "🔗 Enlace: URL directa.",
        "",
        "Hasta 20 enlaces por",
        "mensaje.",
    ])


def download_prompt_text(source: str) -> str:
    if source == "telegram":
        return card("📁 ᴍᴏᴅᴏ ᴛᴇʟᴇɢʀᴀᴍ", [
            "Envía o reenvía el",
            "archivo aquí para",
            "iniciar.",
        ])
    return card("🔗 ᴍᴏᴅᴏ ᴇɴʟᴀᴄᴇ", [
        "Pega aquí una URL",
        "directa.",
        "",
        "Hasta 20 enlaces en",
        "un mensaje.",
    ])


def download_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        btn("⬅️ ᴀᴛʀáꜱ", callback_data="downloads"),
        btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home"),
    ]])


def contact_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]])


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]])


def download_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("📥 Descargar", url=url), btn("📋 Copiar", copy_text=CopyTextButton(text=url))],
    ])


def result_keyboard(url: str, task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("📥 Descargar archivo", url=url)],
        [btn("📋 Copiar enlace", copy_text=CopyTextButton(text=url)),
         btn("📄 Convertir TXT", callback_data=f"j:{task_id}:generate_txt")],
        [btn("🗑️ ʙᴏʀʀᴀʀ ᴅᴇ ʟᴀ ɴᴜʙᴇ", callback_data=f"j:{task_id}:cloud_delete")],
    ])


def result_multi_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("🔗 Enlaces", callback_data=f"j:{task_id}:links"),
         btn("📄 Convertir TXT", callback_data=f"j:{task_id}:generate_txt")],
        [btn("🗑️ ʙᴏʀʀᴀʀ ᴅᴇ ʟᴀ ɴᴜʙᴇ", callback_data=f"j:{task_id}:cloud_delete")],
    ])


def history_detail_keyboard(entry: dict, index: int) -> InlineKeyboardMarkup:
    urls = entry.get("urls", []) if isinstance(entry.get("urls", []), list) else []
    rows = []
    for number, url in enumerate(urls, 1):
        rows.append([btn(f"📥 ᴅᴇꜱᴄᴀʀɢᴀʀ {number}", url=url)])
    if urls:
        rows.append([btn("📋 ᴄᴏᴘɪᴀʀ ᴇɴʟᴀᴄᴇ", copy_text=CopyTextButton(text=urls[0]))])
    rows.append([btn("🗑️ ʙᴏʀʀᴀʀ ᴅᴇʟ ʜɪꜱᴛᴏʀɪᴀʟ", callback_data=f"history:delete:{index}")])
    rows.append([btn("🗑️ ʙᴏʀʀᴀʀ ᴅᴇ ʟᴀ ɴᴜʙᴇ", callback_data=f"history:cloud_delete:{index}")])
    rows.append([btn("⬅️ ᴍɪ ɴᴜʙᴇ ☁️", callback_data="open_history")])
    return InlineKeyboardMarkup(rows)


def storage_expiry(user_id: int, completed_at: datetime | None = None) -> datetime:
    plan = get_plan_info(get_user_plan(user_id))
    base = completed_at or datetime.now(timezone.utc)
    return base + timedelta(hours=int(plan.get("storage_hours", 12)))


def expiry_label(expires_at: str | None) -> str:
    if not expires_at:
        return "No definida"
    try:
        expiry = datetime.fromisoformat(expires_at)
        remaining = max(0, int((expiry - datetime.now(timezone.utc)).total_seconds()))
        hours, rem = divmod(remaining, 3600)
        minutes = rem // 60
        return f"{expiry.strftime('%d/%m/%Y %H:%M UTC')} ({hours}h {minutes:02d}m restantes)"
    except Exception:
        return "No definida"


def transfer_complete_text(filename: str = "", size: int = 0, parts: int = 1,
                           username: str | None = None, user_id: int | None = None,
                           task_id: str | None = None, duration: float | None = None,
                           expires_at: str | None = None) -> str:
    header_label = format_media_header(filename)
    lines = [
        "Ya está disponible en la nube.",
        "",
        header_label,
        f"📦 Tamaño: {_size_label(size)}",
        f"⏱️ Duración: {_duration_label(duration)}",
        f"☁️ Enlace expira: {expiry_label(expires_at)}",
        "",
        "Usa los botones para descargar, copiar, convertir o borrar.",
    ]
    return card("✅ ᴀʀᴄʜɪᴠᴏ ʟɪꜱᴛᴏ", lines)


def admin_panel_text() -> str:
    lines = [
        "Planes configurados:",
        "",
        f"🆓 Gratis: {MAX_FILE_MB_FREE / 1024:.1f} GB/día",
        "⭐ VIP Básico: 10 GB (250$)",
        "💎 VIP Medio: 15 GB (500$)",
        "👑 Premium: Ilimitado (1000$)",
        "",
        "Selecciona una acción:",
    ]
    box = card("⚙️ ᴘᴀɴᴇʟ ᴅᴇ ᴀᴅᴍɪɴ", lines)
    return f"{box}\n\n{BOT_FOOTER}"


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [btn("💸 ᴅᴀʀ ꜱᴀʟᴅᴏ ᴀ ᴜɴ ɪᴅ", callback_data="admin:balance")],
        [btn("🆓 ᴅᴀʀ ɢʀᴀᴛɪꜱ", callback_data="admin:plan:free")],
        [btn("⭐ ᴅᴀʀ ᴠɪᴘ ʙáꜱɪᴄᴏ (250$)", callback_data="admin:plan:vip_basic")],
        [btn("💎 ᴅᴀʀ ᴠɪᴘ ᴍᴇᴅɪᴏ (500$)", callback_data="admin:plan:vip_medium")],
        [btn("👑 ᴅᴀʀ ᴘʀᴇᴍɪᴜᴍ (1000$)", callback_data="admin:plan:premium")],
        [btn("🔍 ᴄᴏɴꜱᴜʟᴛᴀʀ ᴜꜱᴜᴀʀɪᴏ", callback_data="admin:check")],
        [btn("👥 ᴜꜱᴜᴀʀɪᴏꜱ ʀᴇɢɪꜱᴛʀᴀᴅᴏꜱ", callback_data="admin:users:0")],
        [btn("🗂️ ʜɪꜱᴛᴏʀɪᴀʟ ᴅᴇ ᴜꜱᴜᴀʀɪᴏ", callback_data="admin:user_history")],
        [btn("🧹 ʙᴏʀʀᴀʀ ᴛᴏᴅᴏ ᴇʟ ʜɪꜱᴛᴏʀɪᴀʟ", callback_data="admin:all_history_confirm")],
        [btn("📊 ᴇꜱᴛᴀᴅíꜱᴛɪᴄᴀꜱ", callback_data="admin:stats")],
        [btn("📈 ᴛᴏᴘ ᴅᴇ ᴜꜱᴏ", callback_data="admin:top")],
        [btn("📢 ᴅɪꜰᴜꜱɪóɴ", callback_data="admin:broadcast")],
        [btn("🧾 ʀᴇᴘᴏʀᴛᴇ ᴀᴄᴜᴍᴜʟᴀᴛɪᴠᴏ", callback_data="admin:report")],
        [btn("📖 ᴛᴜᴛᴏʀɪᴀʟ ᴅᴇ ᴜꜱᴏ", callback_data="admin:tutorial")],
        [btn("❌ ᴄᴇʀʀᴀʀ ᴘᴀɴᴇʟ", callback_data="home")],
    ])


def admin_duration_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            btn("📅 7 ᴅíᴀꜱ", callback_data=f"admin:dur:{plan_key}:7"),
            btn("📅 15 ᴅíᴀꜱ", callback_data=f"admin:dur:{plan_key}:15"),
        ],
        [
            btn("📅 30 ᴅíᴀꜱ (1 ᴍᴇꜱ)", callback_data=f"admin:dur:{plan_key}:30"),
            btn("📅 90 ᴅíᴀꜱ (3 ᴍᴇꜱᴇꜱ)", callback_data=f"admin:dur:{plan_key}:90"),
        ],
        [
            btn("📅 180 ᴅíᴀꜱ (6 ᴍᴇꜱᴇꜱ)", callback_data=f"admin:dur:{plan_key}:180"),
            btn("📅 365 ᴅíᴀꜱ (1 ᴀñᴏ)", callback_data=f"admin:dur:{plan_key}:365"),
        ],
        [btn("✏️ ᴅᴜʀᴀᴄɪóɴ ᴘᴇʀꜱᴏɴᴀʟɪᴢᴀᴅᴀ", callback_data=f"admin:dur_custom:{plan_key}")],
        [btn("⬅️ ᴠᴏʟᴠᴇʀ ᴀʟ ᴘᴀɴᴇʟ", callback_data="admin:back")],
    ])


def admin_tutorial_text() -> str:
    lines = [
        "Cómo dar planes:",
        "",
        "1️⃣ Selecciona el plan",
        "   (Básico, Medio, Premium)",
        "",
        "2️⃣ Elige el tiempo:",
        "   - 1 Mes (30 días)",
        "   - 1 Año (365 días)",
        "   - O Personalizado",
        "",
        "3️⃣ Envía el ID del",
        "   usuario de Telegram.",
        "",
        "4️⃣ Confirma y el",
        "   usuario recibirá un",
        "   mensaje automático.",
    ]
    box = card("📖 ᴛᴜᴛᴏʀɪᴀʟ ᴅᴇ ᴀᴅᴍɪɴ", lines)
    return f"{box}\n\n{BOT_FOOTER}"


HELP_PAGES = [
    ("📘 ɢᴜíᴀ ʀáᴘɪᴅᴀ 1/4", [
        "¿Qué hace este bot?",
        "",
        "Sube tus archivos a",
        "la nube de ToDus Cuba y",
        "te genera enlace directo.",
        "",
        "⚡ Rápido y seguro.",
    ]),
    ("📁 ᴇɴᴠɪᴀʀ ᴀʀᴄʜɪᴠᴏꜱ 2/4", [
        "Paso a paso:",
        "",
        "1️⃣ Pulsa Descargas",
        "2️⃣ Elige Telegram",
        "3️⃣ Envía el archivo",
        "4️⃣ Espera tu enlace",
        "",
        "Soporta videos, audios,",
        "documentos y fotos.",
    ]),
    ("🔗 ᴇɴᴠɪᴀʀ ᴇɴʟᴀᴄᴇꜱ 3/4", [
        "Paso a paso:",
        "",
        "1️⃣ Pulsa Descargas",
        "2️⃣ Elige Enlace",
        "3️⃣ Pega la URL directa",
        "4️⃣ Espera tu enlace",
        "",
        "Hasta 20 enlaces por",
        "mensaje.",
    ]),
    ("💡 ᴛɪᴘꜱ ʏ ᴄᴏᴍᴀɴᴅᴏꜱ 4/4", [
        "Comandos útiles:",
        "",
        "/cola · tareas activas",
        "/historial · anteriores",
        "/micuota · estado plan",
        "/id · tu ID numérico",
        "/backup · crear respaldo",
        "/restore · restaurar datos",
        "",
        "Dudas: Pulsa Soporte.",
    ]),
]


def help_keyboard(page: int) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(btn("⬅️ ᴀɴᴛᴇʀɪᴏʀ", callback_data=f"help:{page - 1}"))
    if page < len(HELP_PAGES) - 1:
        row.append(btn("➡️ ꜱɪɢᴜɪᴇɴᴛᴇ", callback_data=f"help:{page + 1}"))
    return InlineKeyboardMarkup([row, [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]])


def help_page_text(page: int) -> str:
    title, lines = HELP_PAGES[page]
    box = card(title, lines)
    return f"{box}\n\n{BOT_FOOTER}"


def task_keyboard(job: TransferTask, *, show_manage: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if job.state in {"queued", "downloading", "uploading", "cancelling"}:
        rows.append([btn("⏸️ ᴘᴀᴜꜱᴀʀ", callback_data=f"j:{job.task_id}:cancel")])
    elif job.state == "done":
        links = sorted(job.part_urls.items())
        if len(links) == 1:
            rows.append([btn("📥 Archivo", url=links[0][1])])
            rows.append([btn("📋 Copiar", copy_text=CopyTextButton(text=links[0][1])),
                         btn("📄 Convertir TXT", callback_data=f"j:{job.task_id}:generate_txt")])
            rows.append([btn("🗑️ Borrar", callback_data=f"j:{job.task_id}:cloud_delete")])
        elif links:
            rows.append([btn("🔗 Enlaces", callback_data=f"j:{job.task_id}:links"),
                         btn("📄 Convertir TXT", callback_data=f"j:{job.task_id}:generate_txt")])
            rows.append([btn("🗑️ Borrar", callback_data=f"j:{job.task_id}:cloud_delete")])
    elif job.state in {"error", "cancelled", "paused"}:
        rows.append([btn("▶️ ʀᴇᴀɴᴜᴅᴀʀ", callback_data=f"j:{job.task_id}:retry")])
        if job.part_urls:
            rows.append([btn("🔗 ᴇɴʟᴀᴄᴇꜱ ʟɪꜱᴛᴏꜱ", callback_data=f"j:{job.task_id}:links")])
    if show_manage and job.state in {"done", "error", "cancelled", "paused"}:
        rows.append([btn("🗑️ ʙᴏʀʀᴀʀ ᴛᴀʀᴇᴀ", callback_data=f"j:{job.task_id}:delete")])
    return InlineKeyboardMarkup(rows)


def task_state_label(state: str) -> str:
    return {
        "queued": "⏳ En cola",
        "downloading": "📥 Descargando",
        "uploading": "📤 Subiendo",
        "cancelling": "🚫 Cancelando",
        "done": "✅ Listo",
        "error": "❌ Error",
        "cancelled": "🚫 Cancelado",
        "paused": "⏸️ Pausado",
    }.get(state, state)


def task_detail_text(job: TransferTask) -> str:
    lines = [
        f"📌 Estado: {task_state_label(job.state)}",
    ]
    if job.filename:
        lines.append("📄 Archivo:")
        lines.append(f"{job.filename[:30]}")
    if job.size:
        lines.append(f"📦 Tamaño: {_size_label(job.size)}")
    if job.error:
        lines.append("")
        lines.append(f"⚠️ Detalle: {job.error[:120]}")
    return card("📋 ꜰɪᴄʜᴀ ᴅᴇ ᴛᴀʀᴇᴀ", lines)


async def show_task(job: TransferTask, *, target=None) -> None:
    target = target or job.status_message
    await target.edit_text(task_detail_text(job), reply_markup=task_keyboard(job, show_manage=True))


async def send_task_links(job: TransferTask, bot_obj, chat_id: int | None = None) -> None:
    target_chat = chat_id or job.chat_id
    urls = sorted(job.part_urls.items())
    if not urls:
        await bot_obj.send_message(chat_id=target_chat, text=sc("No hay enlaces."))
        return
    total = len(urls)
    for i, url in urls:
        part_name = _part_filename(job.filename or "archivo", i + 1, total)
        await bot_obj.send_message(
            chat_id=target_chat,
            text=card(f"📎 ᴘᴀʀᴛᴇ {i + 1}/{total}", [part_name, "", url]),
            reply_markup=download_keyboard(url),
            disable_web_page_preview=True,
        )


async def _edit_task_status(job: TransferTask, text: str) -> None:
    try:
        await job.status_message.edit_text(text, reply_markup=task_keyboard(job))
    except Exception:
        pass


async def enqueue_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE, *,
                           source_kind: str, source_url: str | None = None) -> None:
    message, user = update.effective_message, update.effective_user
    if not message or not user:
        return
    placeholder = await message.reply_text(
        card("⏳ ᴇɴ ᴄᴏʟᴀ", ["Esperando turno..."]),
    )
    job = TransferTask(
        user_id=user.id, chat_id=message.chat_id, source_kind=source_kind,
        source_message=message, status_message=placeholder, source_url=source_url,
        username=f"@{user.username}" if user.username else None,
        display_name=getattr(user, "full_name", None),
    )
    manager: FairTaskQueue = context.application.bot_data["task_queue"]
    if not await manager.enqueue(job, get_user_queue_limit(user.id)):
        await placeholder.edit_text(
            card("🚫 ᴄᴜᴘᴏ ᴄᴏᴍᴘʟᴇᴛᴏ", [
                f"Tu plan permite {get_user_queue_limit(user.id)} tareas",
                "en tu cola personal.",
                "",
                "Espera a que termine una",
                "o mejora tu plan.",
            ]),
        )
        return
    await _edit_task_status(job, card("⏳ ᴇɴ ᴄᴏʟᴀ", ["Esperando turno..."]))


async def process_task(job: TransferTask, application: Application) -> None:
    if job.cancel_requested:
        job.set_state("paused")
        await _edit_task_status(job, task_detail_text(job))
        return
    temp_path = Path(job.temp_path) if job.temp_path else None
    progress_state = {"started": time.monotonic(), "last": 0.0, "last_bucket": -1}

    async def report_download_progress(received, total):
        now = time.monotonic()
        percent = min(100, int(received * 100 / total)) if total else 0
        bucket = percent // 5
        if (total and percent < 100 and bucket <= progress_state["last_bucket"]) or now - progress_state["last"] < 1.5:
            return
        if progress_state["last"] == 0:
            progress_state["started"] = now
        progress_state["last"] = now
        progress_state["last_bucket"] = bucket
        elapsed = max(0.1, now - progress_state["started"])
        speed = received / MIB / elapsed
        eta = (total - received) / (speed * MIB) if total and speed > 0 else None
        curr_fname = job.filename or ""
        if not curr_fname and job.source_message:
            for mtype in ("document", "video", "audio", "animation", "photo"):
                m = getattr(job.source_message, mtype, None)
                if m:
                    curr_fname = getattr(m, "file_name", None) or ("photo.jpg" if mtype == "photo" else "")
                    if curr_fname:
                        break
        try:
            await job.status_message.edit_text(
                download_progress_text(received, total, speed, eta, filename=curr_fname, source_url=job.source_url),
                reply_markup=task_keyboard(job),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    try:
        max_bytes = 4096 * MIB
        if temp_path is None or not temp_path.exists() or not job.download_complete:
            job.set_state("downloading")
            await _edit_task_status(job, card("📥 ᴅᴇꜱᴄᴀʀɢᴀɴᴅᴏ", [
                "Iniciando descarga...",
            ]))
            if job.source_kind == "url":
                source_url = job.source_url or ""
                seconds = MAX_TRANSFER_HOURS * 3600
                if callable(download_platform_video) and is_supported_platform_url(source_url):
                    job.set_state("downloading")
                    await _edit_task_status(job, card("📥 ᴅᴇꜱᴄᴀʀɢᴀɴᴅᴏ", [
                        "Descargando vídeo...",
                        "Procesando con yt-dlp...",
                    ]))
                    ytdlp_work_dir = Path(TMPDIR) / f"ytdlp-{job.task_id}"
                    loop = asyncio.get_running_loop()
                    def ytdlp_progress(downloaded, total):
                        try:
                            asyncio.run_coroutine_threadsafe(
                                report_download_progress(downloaded, total),
                                loop
                            )
                        except Exception:
                            pass
                    temp_path, filename, size = await asyncio.to_thread(
                        download_platform_video,
                        source_url,
                        ytdlp_work_dir,
                        max_bytes=max_bytes,
                        max_duration_seconds=seconds,
                        progress_hook=ytdlp_progress,
                        is_cancelled=lambda: job.cancel_requested,
                    )
                else:
                    if temp_path is None:
                        partial = tempfile.NamedTemporaryFile(prefix="tg-download-", suffix=".part", dir=TMPDIR, delete=False)
                        partial.close()
                        temp_path = Path(partial.name)
                        job.temp_path = str(temp_path)
                    connector = aiohttp.TCPConnector(
                        resolver=PublicOnlyResolver(),
                        use_dns_cache=True,
                        ttl_dns_cache=600,
                        limit=0,
                        keepalive_timeout=90,
                        enable_cleanup_closed=True,
                    )
                    async with aiohttp.ClientSession(
                        connector=connector,
                        timeout=aiohttp.ClientTimeout(total=seconds, connect=30, sock_read=180),
                        trust_env=False,
                        auto_decompress=False,
                        read_bufsize=16 * 1024 * 1024,
                        headers={
                            "Accept-Encoding": "identity",
                            "User-Agent": "JK-Bot/2.8-Turbo (High-Speed Downloader)",
                            "Connection": "keep-alive",
                        },
                    ) as session:
                        temp_path, filename, size = await download_to_temp(
                            session, source_url, report_download_progress, max_bytes,
                            is_cancelled=lambda: job.cancel_requested,
                            partial_path=temp_path,
                        )
            else:
                temp_path, filename, size = await download_telegram_media(
                    job.source_message, application.bot_data.get("mtproto_client"),
                    report_download_progress,
                    local_bot_api=application.bot_data.get("local_bot_api", False),
                    mtproto_message_cache=application.bot_data.get("mtproto_message_cache"),
                )
            job.temp_path, job.filename, job.size = str(temp_path), filename, size
            job.download_complete = True
        else:
            filename, size = job.filename or temp_path.name, job.size or temp_path.stat().st_size

        validate_downloaded_file(temp_path, filename)

        if size > max_bytes and not is_owner(job.user_id):
            temp_path.unlink(missing_ok=True)
            job.temp_path = None
            raise ValueError(f"Supera {_size_label(max_bytes, 0)}")

        ok, err_msg = check_quota(job.user_id, size)
        if not ok:
            job.error = "Cuota agotada"
            job.set_state("error")
            try:
                await job.status_message.edit_text(err_msg, reply_markup=quota_exhausted_keyboard())
            except Exception:
                await _edit_task_status(job, err_msg)
            return

        if job.cancel_requested:
            job.set_state("paused")
            await _edit_task_status(job, task_detail_text(job))
            return

        part_size = 1900 * MIB
        if not job.part_paths or any(not Path(p).exists() for p in job.part_paths):
            part_dir = Path(TMPDIR) / f"jk-task-{job.task_id}"
            parts = await asyncio.to_thread(split_into_parts, temp_path, filename, part_dir, part_size)
            job.part_paths = [str(p) for p in parts]
        for index, part_path_str in enumerate(job.part_paths):
            if index in job.part_urls:
                continue
            if job.cancel_requested:
                job.set_state("paused")
                await _edit_task_status(job, task_detail_text(job))
                return
            part_path = Path(part_path_str)
            part_name = _part_filename(filename, index + 1, len(job.part_paths))
            job.set_state("uploading")
            await _edit_task_status(job, card("📤 ꜱᴜʙɪᴇɴᴅᴏ", [
                part_name[:24],
                f"Parte {index + 1}/{len(job.part_paths)}",
            ]))
            try:
                part_total = part_path.stat().st_size
            except OSError:
                part_total = 0
            if part_total:
                try:
                    await job.status_message.edit_text(
                        upload_progress_text(0, part_total, filename=part_name),
                        reply_markup=task_keyboard(job),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass
            link, _ = await upload_to_todus_s3_with_progress(
                job.status_message, part_path, part_name, job.user_id,
                reply_markup=lambda: task_keyboard(job),
                is_cancelled=lambda: job.cancel_requested,
            )
            job.part_urls[index] = link
            if job.cancel_requested:
                job.set_state("paused")
                await _edit_task_status(job, task_detail_text(job))
                return

        try:
            add_daily_usage(job.user_id, size)
        except Exception:
            pass

        # Guardar en CLOUD_CACHE_DIR para auto-renovación silenciosa durante todo el plan
        cached_paths = []
        try:
            CLOUD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            source_files = job.part_paths if (job.part_paths and len(job.part_paths) > 1) else ([temp_path] if temp_path else [])
            for idx, p in enumerate(source_files):
                if p and Path(p).is_file():
                    safe_part_name = clean_filename(Path(p).name)
                    target_cache = CLOUD_CACHE_DIR / f"{job.task_id}_p{idx}_{safe_part_name}"
                    shutil.copy2(p, target_cache)
                    cached_paths.append(str(target_cache))
        except Exception as cache_err:
            log.warning("Aviso guardando en cloud cache: %s", cache_err)

        completed_at = datetime.now(timezone.utc)
        expires_at = storage_expiry(job.user_id, completed_at).isoformat()
        try:
            save_task_history(job.user_id, {
                "task_id": job.task_id,
                "filename": filename,
                "size": size,
                "parts": len(job.part_urls),
                "urls": [job.part_urls[i] for i in sorted(job.part_urls.keys())],
                "completed_at": completed_at.isoformat(),
                "expires_at": expires_at,
                "storage_duration_hours": get_plan_info(get_user_plan(job.user_id)).get("storage_hours", 12),
                "duration": max(0, job.updated_at - job.created_at),
                "state": "done",
                "storage_backend": "todus_s3",
                "source_kind": job.source_kind,
                "cached_paths": cached_paths,
                "chat_id": getattr(job.status_message, "chat_id", None) if job.status_message else None,
                "message_id": getattr(job.status_message, "message_id", None) if job.status_message else None,
            })
        except Exception:
            pass

        schedule_data_backup(application, "subida completada")
        job.set_state("done")
        links = sorted(job.part_urls.items())
        if len(links) == 1:
            final_keyboard = result_keyboard(links[0][1], job.task_id)
        else:
            final_keyboard = result_multi_keyboard(job.task_id)
        await job.status_message.edit_text(
            transfer_complete_text(
                filename=filename,
                size=size,
                parts=len(job.part_urls),
                duration=max(0, job.updated_at - job.created_at),
                expires_at=expires_at,
            ),
            reply_markup=final_keyboard,
            disable_web_page_preview=True,
        )
        if temp_path:
            temp_path.unlink(missing_ok=True)
            job.temp_path = None
        if job.part_paths and len(job.part_paths) > 1:
            shutil.rmtree(Path(job.part_paths[0]).parent, ignore_errors=True)
    except Exception as exc:
        log.exception("Transfer failed user=%s task=%s", job.user_id, job.task_id)
        if job.cancel_requested:
            job.set_state("paused")
        else:
            error_text = str(exc)
            job.error = error_text[:200]
            job.set_state("error")
        await _edit_task_status(job, task_detail_text(job))


async def task_worker(application: Application) -> None:
    manager: FairTaskQueue = application.bot_data["task_queue"]
    while True:
        job = await manager.take()
        try:
            await process_task(job, application)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.exception(f"Error procesando tarea en worker: {exc}")
        finally:
            manager.task_finished(job)

def render_queue_view(user_id: int, manager: FairTaskQueue) -> tuple[str, InlineKeyboardMarkup]:
    local_active = manager.get_local_active(user_id)
    local_queued = manager.get_local_queued(user_id)
    local_paused = manager.get_local_paused(user_id)
    global_active = manager.get_global_active_count()
    global_users = manager.get_global_active_users_count()

    lines = [
        "👤 ᴄᴏʟᴀ ʟᴏᴄᴀʟ (ᴛᴜ ᴄᴏʟᴀ)",
        f"⚡ Activas tuyas: {len(local_active)}",
        f"⏳ En espera: {len(local_queued)}",
    ]
    if local_paused:
        lines.append(f"⏸️ Pausadas: {len(local_paused)} (no ocupan cola)")
    
    lines.extend([
        "",
        "🌐 ᴄᴏʟᴀ ɢʟᴏʙᴀʟ (ʙᴏᴛ ᴇɴ ᴠɪᴠᴏ)",
        f"🚀 Activas en el bot: {global_active}",
        f"👥 Usuarios transfiriendo: {global_users}",
        "",
        "💡 Tu cola es personal: no tienes que",
        "esperar a que otros usuarios terminen.",
    ])
    
    rows = []
    for j in (local_active + local_queued)[:5]:
        name = (j.filename or j.source_url or "Tarea")[:16]
        rows.append([btn(f"{task_state_label(j.state)} - {name}", callback_data=f"j:{j.task_id}:open")])
        
    if local_paused:
        rows.append([btn(f"⏸️ Ver pausadas ({len(local_paused)})", callback_data="queue:paused")])

    rows.append([
        btn("🔄 ᴀᴄᴛᴜᴀʟɪᴢᴀʀ ᴄᴏʟᴀ", callback_data="open_queue"),
        btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home"),
    ])
    box = card("📋 ɢᴇꜱᴛᴏʀ ᴅᴇ ᴄᴏʟᴀꜱ", lines)
    return f"{box}\n\n{BOT_FOOTER}", InlineKeyboardMarkup(rows)


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_update(update):
        return
    message, user = update.effective_message, update.effective_user
    if not message or not user:
        return
    if not await ensure_membership(update, context):
        return
    manager: FairTaskQueue = context.application.bot_data["task_queue"]
    text, markup = render_queue_view(user.id, manager)
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_private_update(update):
        return
    message, user = update.effective_message, update.effective_user
    if not message or not user:
        return
    if not await ensure_membership(update, context):
        return
    persistent = get_task_history(user.id, 15)
    if not persistent:
        await message.reply_text(
            card("☁️ ᴍɪ ɴᴜʙᴇ", ["No tienes historial", "todavía."]),
            reply_markup=home_keyboard(),
        )
        return
    lines = []
    for number, entry in enumerate(persistent[:10], 1):
        try:
            dt = datetime.fromisoformat(entry["completed_at"]).strftime("%d/%m %H:%M")
        except Exception:
            dt = "—"
        name = (entry.get("filename") or "Archivo")[:20]
        lines.append(f"{number}. ✅ {name}")
        lines.append(f"   {dt} · {_size_label(entry.get('size', 0), 1)}")
    box = card("☁️ ᴍɪ ɴᴜʙᴇ", lines or ["Sin registros."])
    rows = []
    for number, entry in enumerate(persistent[:5], 1):
        name = (entry.get("filename") or "Archivo")[:18]
        urls = entry.get("urls", [])
        if urls:
            rows.append([btn(f"📎 {number}. {name}", callback_data=f"history:view:{number - 1}")])
    rows.append([btn("🗑️ ᴠᴀᴄɪᴀʀ ɴᴜʙᴇ", callback_data="history:delete_menu")])
    rows.append([btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")])
    await message.reply_text(
        f"{box}\n\n{BOT_FOOTER}",
        reply_markup=InlineKeyboardMarkup(rows),
        disable_web_page_preview=True,
    )


async def downloads_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    if update.effective_message and await ensure_membership(update, context):
        await update.effective_message.reply_text(
            download_menu_text(), reply_markup=download_menu_keyboard(),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    if update.effective_message and await ensure_membership(update, context):
        await update.effective_message.reply_text(help_page_text(0), reply_markup=help_keyboard(0))


async def my_quota_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    if not user or not update.effective_message:
        return
    if not await ensure_membership(update, context):
        return
    box = card("📊 ᴍɪ ᴄᴜᴏᴛᴀ", quota_lines(user.id))
    await update.effective_message.reply_text(
        f"{box}\n\n{BOT_FOOTER}",
        reply_markup=home_keyboard(),
    )


def welcome_text(user_id: int, user_name: str, username: str | None = None) -> str:
    short_name = (user_name or "Usuario").split()[0][:14]
    username_label = f"@{username}" if username else "sin @usuario"
    identity_lines = [
        f"👤 Nombre: {user_name or 'Usuario'}",
        f"🔗 Usuario: {username_label}",
        f"🆔 ID: {{mono:{user_id}}}",
        "",
    ]
    if is_owner(user_id):
        lines = [
            f"👋 Hola, {short_name}",
            "",
            *identity_lines,
            f" Plan: 🜲 Plan Creador",
            f"📦 Disponible: ∞ GB",
            f"⏳ Acceso: Permanente",
            "",
            "📥 Envía un archivo o",
            "   pega un enlace para",
            "   subirlo a la nube.",
            "",
            "👑 Modo Creador Activo",
        ]
        return card_with_credit(BOT_NAME, lines)
    plan = get_plan_info(get_user_plan(user_id))
    remaining = get_remaining_quota(user_id)
    lines = [
        f"👋 Hola, {short_name}",
        "",
        *identity_lines,
        f" Plan: {plan['badge']} {plan['display']}",
        f"💸 Saldo: {get_user_balance(user_id)}$",
        f"📦 Disponible: {remaining / GIB:.2f} GB",
    ]
    if plan["rank"] > 0:
        _, rem_days = get_plan_expiry_info(user_id)
        if rem_days is not None:
            lines.append(f"⏳ Días restantes: {rem_days}")
    lines += [
        "",
        "📥 Envía un archivo o",
        "   pega un enlace para",
        "   subirlo a la nube.",
        "",
        "🔥 Rápido · Seguro",
    ]
    return card_with_credit(BOT_NAME, lines)


def membership_keyboard(channel_label: str = "Canal", group_label: str = "Grupo") -> InlineKeyboardMarkup:
    ch_url = CHANNEL_JOIN_URL or "https://t.me/gg_no_root"
    grp_url = GROUP_JOIN_URL or "https://t.me/videogameplay0406"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ᴊᴋ ᴄʜᴀɴɴᴇʟꫂꤪꤨᴼᶠᶜ", url=ch_url)],
        [InlineKeyboardButton("ᴊᴋ ᴄʜᴀᴛꫂꤪꤨᴼᶠᶜ", url=grp_url)],
        [InlineKeyboardButton("ʏᴀ ᴍᴇ ᴜɴɪ ✅", callback_data="membership:verify")],
    ])

def membership_prompt_text(channel_label: str = "canal", group_label: str = "grupo") -> str:
    return (
        "<b>Verificación ✅</b>\n\n"
        "Para Continuar Debes Unirte\n\n"
        "Cuando te unas presiona\n"
        "&lt;Ya me uni&gt;"
    )

async def required_chat_labels(bot_obj) -> tuple[str, str]:
    return "ᴊᴋ ᴄʜᴀɴɴᴇʟꫂꤪꤨᴼᶠᶜ", "ᴊᴋ ᴄʜᴀᴛꫂꤪꤨᴼᶠᶜ"

def membership_error_text() -> str:
    return (
         "<b>Verificación ✅</b>\n\n"
        "Para Continuar Debes Unirte\n\n"
        "Cuando te unas presiona\n"
        "&lt;Ya me uni&gt;"
    )

def membership_missing_text(labels: list[str]) -> str:
    return (
        "<b>Verificación ✅</b>\n\n"
        "Para Continuar Debes Unirte\n\n"
        "Cuando te unas presiona\n"
        "&lt;Ya me uni&gt;"
    )
    return card("🚫 ᴀᴄᴄᴇꜱᴏ ʀᴇꜱᴛʀɪɴɢɪᴅᴏ", lines)


async def check_required_memberships_detailed(bot_obj, user_id: int) -> tuple[bool, bool, list[str]]:
    required = [chat for chat in (REQUIRED_CHANNEL, REQUIRED_GROUP) if chat]
    labels = [str(chat) if str(chat).startswith("@") else "el canal configurado" for chat in required]
    missing: list[str] = []
    failed = False

    async def check_one(index: int, chat_id: str):
        nonlocal failed
        try:
            member = await asyncio.wait_for(
                bot_obj.get_chat_member(chat_id=chat_id, user_id=user_id),
                timeout=8,
            )
            status = getattr(member, "status", "")
            is_member = status in {"creator", "administrator", "member"}
            if status == "restricted":
                is_member = bool(getattr(member, "is_member", False))
            if not is_member:
                missing.append(labels[index] if index < len(labels) else str(chat_id))
        except Exception:
            failed = True

    await asyncio.gather(*(check_one(index, chat_id) for index, chat_id in enumerate(required)))
    return not missing and not failed, failed, missing


async def user_has_required_memberships(bot_obj, user_id: int) -> bool:
    is_member, check_failed, _ = await check_required_memberships_detailed(bot_obj, user_id)
    return is_member and not check_failed


async def ensure_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not is_private_update(update):
        return False
    user = update.effective_user
    if not user or is_owner(user.id):
        return True
    register_user(user)
    is_member, check_failed, missing = await check_required_memberships_detailed(context.bot, user.id)
    if is_member:
        return True
    message = update.effective_message
    if message:
        if check_failed:
            await message.reply_text(membership_error_text(), reply_markup=membership_keyboard())
            return False
        channel_label, group_label = await required_chat_labels(context.bot)
        await message.reply_text(
            membership_missing_text(missing) + "\n\n" + membership_prompt_text(channel_label, group_label),
            reply_markup=membership_keyboard(channel_label, group_label),
        )
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    if not user or not update.effective_message:
        return
    if not await ensure_membership(update, context):
        return
    referral_notice = ""
    args = getattr(context, "args", []) or []
    if args:
        match = re.fullmatch(r"ref_(\d+)", str(args[0]).strip(), re.IGNORECASE)
        if match:
            referrer_id = int(match.group(1))
            if user.id == referrer_id:
                referral_notice = "\n\n⚠️ No puedes usar tu propio enlace de invitación."
            else:
                users_data = _load_json(USERS_DATA_FILE).get("users", {})
                user_entry = users_data.get(str(user.id), {}) if isinstance(users_data, dict) else {}
                if user_entry.get("referred_by") or user_entry.get("referral_rewarded"):
                    referral_notice = "\n\n⚠️ Ya eres usuario de este bot y utilizaste un enlace de invitación anteriormente."
                elif str(user.id) in users_data and user_entry.get("first_seen"):
                    referral_notice = "\n\n⚠️ Ya eres usuario registrado de este bot. Los enlaces de invitación solo son válidos para nuevos miembros."
                elif apply_referral(user.id, referrer_id):
                    referral_notice = "\n\n🎁 Recibiste 5$ de bienvenida por entrar con un enlace de invitación."
                    try:
                        await context.bot.send_message(
                            chat_id=referrer_id,
                            text=card("🎉 ʀᴇꜰᴇʀɪᴅᴏ ᴄᴏɴꜰɪʀᴍᴀᴅᴏ", [
                                "Alguien entró con tu enlace.",
                                "🎊 ¡Felicidades! Recibiste 5$.",
                                f"💳 Saldo actual: {get_user_balance(referrer_id)}$",
                            ]),
                        )
                    except Exception:
                        pass
                    schedule_data_backup(context.application, "recompensa de referido")
                else:
                    referral_notice = "\n\n⚠️ Ya eres usuario de este bot o el enlace ya no es válido." 
    await update.effective_message.reply_text(
        welcome_text(
            user.id,
            getattr(user, "full_name", "") or getattr(user, "first_name", ""),
            getattr(user, "username", None),
        ) + referral_notice,
        reply_markup=main_keyboard(user.id),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    if user and update.effective_message:
        if not await ensure_membership(update, context):
            return
        username = f"@{user.username}" if user.username else "sin @usuario"
        await update.effective_message.reply_text(
            card("👤 ᴛᴜ ᴜꜱᴜᴀʀɪᴏ ʏ ᴛᴜ ɪᴅ", [
                f"Usuario: {{mono:{username}}}",
                f"ID de Telegram: {{mono:{user.id}}}",
            ]),
        )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not await ensure_membership(update, context):
        return
    await message.reply_text(
        public_leaderboard_text(),
        reply_markup=InlineKeyboardMarkup([[btn("?? ɪɴɪᴄɪᴏ", callback_data="home")]]),
    )


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ejecuta una copia completa a TELEGRAM_BACKUP_CHAT_ID y envía el archivo ZIP al creador."""
    if not is_private_update(update):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_owner(user.id):
        return
    chat_id = configured_backup_chat_id()
    layout = context.application.bot_data.get("telegram_backup_layout")
    if not chat_id or layout is None:
        await message.reply_text(sc("Respaldo no configurado."))
        return

    status_msg = await message.reply_text(sc("⏳ Generando respaldo cifrado..."))
    lock = context.application.bot_data.get("telegram_backup_lock") or asyncio.Lock()
    async with lock:
        success = await backup_to_telegram(
            context.bot,
            getattr(context.bot, "token", ""),
            chat_id,
            layout,
            logger=log,
        )

    if success:
        await status_msg.edit_text(
            card("✅ ʀᴇꜱᴘᴀʟᴅᴏ ᴄᴏᴍᴘʟᴇᴛᴀᴅᴏ", [
                f"Destino: {{mono:{chat_id}}}",
                "El respaldo ha sido enviado",
                "y fijado en Telegram.",
                "",
                "Al migrar a otro hosting,",
                "tus datos se restaurarán",
                "automáticamente al iniciar.",
            ])
        )
    else:
        await status_msg.edit_text(sc("❌ No se pudo completar el respaldo. Revisa permisos."))


async def restore_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Restaura los datos locales descargando el respaldo desde TELEGRAM_BACKUP_CHAT_ID."""
    if not is_private_update(update):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_owner(user.id):
        return
    chat_id = configured_backup_chat_id()
    layout = context.application.bot_data.get("telegram_backup_layout")
    if not chat_id or layout is None:
        await message.reply_text(sc("Canal de respaldo no configurado."))
        return

    status_msg = await message.reply_text(sc("⏳ Buscando y descargando respaldo de Telegram..."))
    files, bytes_restored = await restore_from_telegram(
        context.bot,
        getattr(context.bot, "token", ""),
        chat_id,
        layout,
        logger=log,
    )
    if files > 0:
        await status_msg.edit_text(
            card("✅ ᴅᴀᴛᴏꜱ ʀᴇꜱᴛᴀᴜʀᴀᴅᴏꜱ", [
                f"Archivos restaurados: {files}",
                f"Tamaño total: {bytes_restored / 1024:.1f} KB",
                "",
                "Todos los usuarios, saldos,",
                "planes e historial están",
                "completamente activos.",
            ])
        )
    else:
        await status_msg.edit_text(
            card("⚠️ ꜱɪɴ ʀᴇꜱᴘᴀʟᴅᴏ", [
                "No se encontró un respaldo",
                "fijado en el canal.",
                "Usa /backup primero.",
            ])
        )


async def jkadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    user = update.effective_user
    message = update.effective_message
    if not user or not message or not is_owner(user.id):
        return
    if not await ensure_membership(update, context):
        return
    await message.reply_text(
        admin_panel_text(),
        reply_markup=admin_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return
    register_user(user)

    if query.data == "membership:verify":
        await query.answer()
        if is_owner(user.id):
            is_member, check_failed, missing = True, False, []
        else:
            is_member, check_failed, missing = await check_required_memberships_detailed(context.bot, user.id)
        if is_member:
            success_text = (
                "✅ Listo\n"
                "───────────────────\n"
                "✅ ¡Verificación exitosa!\n\n"
                "Ya puedes usar el bot normalmente."
            )
            await query.message.edit_text(
                success_text,
                reply_markup=main_keyboard(user.id),
                parse_mode=ParseMode.HTML,
            )
        else:
            channel_label, group_label = await required_chat_labels(context.bot)
            prompt = membership_error_text() if check_failed else (
                membership_missing_text(missing)
                + "\n\n"
                + membership_prompt_text(channel_label, group_label)
            )
            await query.message.edit_text(
                prompt,
                reply_markup=membership_keyboard(channel_label, group_label),
            )
        return

    if query.data in {"balance", "plans", "referral:show"}:
        await query.answer()
        await query.message.edit_text(
            plans_text(user.id, context.application.bot_data.get("bot_username")),
            reply_markup=plans_keyboard(user.id, context.application.bot_data.get("bot_username")),
        )
        return

    if not is_owner(user.id) and not await user_has_required_memberships(context.bot, user.id):
        await query.answer()
        channel_label, group_label = await required_chat_labels(context.bot)
        await query.message.edit_text(
            membership_prompt_text(channel_label, group_label),
            reply_markup=membership_keyboard(channel_label, group_label),
        )
        return
    await query.answer()

    if query.data == "top:users":
        await query.message.edit_text(
            public_leaderboard_text(),
            reply_markup=InlineKeyboardMarkup([[btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")]]),
        )
        return

    if query.data == "plans:buy":
        await query.message.edit_text(
            plan_purchase_text(user.id),
            reply_markup=plan_purchase_keyboard(user.id),
        )
        return

    if query.data.startswith("plans:unavailable:"):
        plan_key = query.data.rsplit(":", 1)[-1]
        plan = PLANS.get(plan_key)
        if plan:
            await query.answer(
                sc(f"Necesitas {plan['price_value']}$ y tienes {get_user_balance(user.id)}$"),
                show_alert=True,
            )
        return

    if query.data.startswith("plans:confirm:"):
        plan_key = query.data.rsplit(":", 1)[-1]
        plan = PLANS.get(plan_key)
        if not plan or plan_key in {"free", "owner"}:
            await query.answer(sc("Plan no disponible"), show_alert=True)
            return
        if get_user_balance(user.id) < plan["price_value"]:
            await query.answer(sc("Tu saldo ya no alcanza para este plan"), show_alert=True)
            await query.message.edit_text(plan_purchase_text(user.id), reply_markup=plan_purchase_keyboard(user.id))
            return
        await query.message.edit_text(
            card("⚠️ ᴄᴏɴꜰɪʀᴍᴀ ᴛᴜ ᴄᴏᴍᴘʀᴀ", [
                f"{plan['badge']} {plan['display']}",
                f"💳 Precio: {plan['price']}",
                f"💸 Saldo después: {get_user_balance(user.id) - plan['price_value']}$",
                f"📦 Cuota: {plan['daily_label']}/día",
                f"☁️ Cada archivo dura: {plan['storage_label']}",
                "",
                "¿Confirmas la compra?",
            ]),
            reply_markup=InlineKeyboardMarkup([
                [btn("✅ ᴄᴏɴꜰɪʀᴍᴀʀ ᴄᴏᴍᴘʀᴀ", callback_data=f"plans:purchase:{plan_key}")],
                [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="plans:buy")],
            ]),
        )
        return

    if query.data.startswith("plans:purchase:"):
        plan_key = query.data.rsplit(":", 1)[-1]
        ok, message = purchase_plan_with_balance(user.id, plan_key)
        if ok:
            schedule_data_backup(context.application, "compra automática de plan")
            plan = PLANS[plan_key]
            await query.message.edit_text(
                card("✅ ᴘʟᴀɴ ᴀᴅQᴜɪʀɪᴅᴏ", [
                    "La compra se realizó correctamente.",
                    f"{plan['badge']} {plan['display']} está activo.",
                    f"💸 Saldo restante: {get_user_balance(user.id)}$",
                    f"📦 Cuota: {plan['daily_label']}/día",
                    f"☁️ Tus archivos durarán {plan['storage_label']} en la nube.",
                ]),
                reply_markup=InlineKeyboardMarkup([
                    [btn("💸 ᴠᴇʀ ᴍɪ ꜱᴀʟᴅᴏ ʏ ᴘʟᴀɴᴇꜱ", callback_data="plans")],
                    [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")],
                ]),
            )
        else:
            await query.answer(sc(message), show_alert=True)
            await query.message.edit_text(plan_purchase_text(user.id), reply_markup=plan_purchase_keyboard(user.id))
        return

    if query.data.startswith("admin:"):
        if not is_owner(user.id):
            await query.answer(sc("Sin acceso"), show_alert=True)
            return

        if query.data == "admin:back":
            context.user_data.pop("admin_state", None)
            await query.message.edit_text(admin_panel_text(), reply_markup=admin_keyboard())
            return

        if query.data == "admin:balance":
            context.user_data["admin_state"] = {"step": "awaiting_balance_user_id"}
            await query.message.edit_text(
                card("💸 ᴅᴀʀ ꜱᴀʟᴅᴏ", [
                    "Envía el ID numérico",
                    "del usuario destinatario.",
                    "",
                    "Después indicarás el monto",
                    "y confirmarás la operación.",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data.startswith("admin:confirm_balance:"):
            parts = query.data.split(":")
            if len(parts) != 4:
                return
            target_id, amount = int(parts[2]), int(parts[3])
            context.user_data.pop("admin_state", None)
            ok, new_balance = grant_user_balance(target_id, amount)
            if not ok:
                await query.answer(sc("No se pudo guardar el saldo"), show_alert=True)
                return
            schedule_data_backup(context.application, "saldo otorgado por admin")
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=card("🎁 ꜱᴀʟᴅᴏ ʀᴇᴄɪʙɪᴅᴏ", [
                        f"Has recibido {amount}$ de saldo.",
                        f"💸 Saldo actual: {new_balance}$",
                    ]),
                )
            except Exception:
                pass
            await query.message.edit_text(
                card("✅ ꜱᴀʟᴅᴏ ᴏᴛᴏʀɢᴀᴅᴏ", [
                    f"ID: {{mono:{target_id}}}",
                    f"Acreditado: {amount}$",
                    f"Saldo actual: {new_balance}$",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:tutorial":
            await query.message.edit_text(
                admin_tutorial_text(),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:stats":
            plan_data = _load_json(PLAN_DATA_FILE)
            users_data = _load_json(USERS_DATA_FILE).get("users", {})
            known_ids = registered_user_ids()
            total_users = len(known_ids)
            today = _today_key()
            active_today = sum(
                1 for uid in known_ids
                if isinstance(users_data, dict)
                and str(uid) in users_data
                and users_data[str(uid)].get("last_seen_date") == today
            )
            by_plan = {}
            for uid in known_ids:
                info = plan_data.get(str(uid), {"plan": "free"})
                p = info.get("plan", "free")
                by_plan[p] = by_plan.get(p, 0) + 1
            lines = [
                f"👥 Usuarios: {total_users}",
                f"🟢 Activos hoy: {active_today}",
                "",
                "Por plan:",
            ]
            for pk, count in sorted(by_plan.items()):
                pi = get_plan_info(pk)
                lines.append(f"{pi['badge']} {pi['display']}: {count}")
            box = card("📊 ᴇꜱᴛᴀᴅíꜱᴛɪᴄᴀꜱ", lines)
            await query.message.edit_text(
                f"{box}\n\n{BOT_FOOTER}",
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:top":
            await query.message.edit_text(
                admin_leaderboard_text(),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data.startswith("admin:plan:"):
            plan_key = query.data.split(":", 2)[2]
            if plan_key not in PLANS:
                return
            if plan_key == "free":
                context.user_data["admin_state"] = {"step": "awaiting_user_id", "plan": "free", "days": 0}
                lines = [
                    "Plan: 🆓 Plan Gratis",
                    "Duración: Permanente",
                    "",
                    "Envía el ID de",
                    "Telegram del usuario.",
                ]
                await query.message.edit_text(
                    card("🆓 ᴀꜱɪɢɴᴀʀ ɢʀᴀᴛɪꜱ", lines),
                    reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
                )
            else:
                plan = get_plan_info(plan_key)
                lines = [
                    f"Plan: {plan['badge']} {plan['display']}",
                    f"Precio: {plan['price']}",
                    f"Cuota: {plan['daily_label']}/día",
                    "",
                    "Selecciona el tiempo",
                    "de duración:",
                ]
                await query.message.edit_text(
                    card(f"⏳ ᴛɪᴇᴍᴘᴏ · {plan['display']}", lines),
                    reply_markup=admin_duration_keyboard(plan_key),
                )
            return

        if query.data.startswith("admin:dur:"):
            parts = query.data.split(":")
            plan_key = parts[2]
            days = int(parts[3])
            context.user_data["admin_state"] = {"step": "awaiting_user_id", "plan": plan_key, "days": days}
            plan = get_plan_info(plan_key)
            lines = [
                f"Plan: {plan['badge']} {plan['display']}",
                f"Duración: {days} días",
                f"Cuota: {plan['daily_label']}/día",
                "",
                "Envía ahora el ID",
                "de Telegram del",
                "usuario.",
            ]
            await query.message.edit_text(
                card("🆔 ɪɴɢʀᴇꜱᴀʀ ᴜꜱᴜᴀʀɪᴏ", lines),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data.startswith("admin:confirm_plan:"):
            parts = query.data.split(":")
            plan_key = parts[2]
            days = int(parts[3])
            target_id = int(parts[4])
            context.user_data.pop("admin_state", None)

            entry = set_user_plan(target_id, plan_key, days if days > 0 else None)
            record_admin_audit(user.id, target_id, plan_key, days if days > 0 else None)
            schedule_data_backup(context.application, "cambio de plan")
            plan = get_plan_info(plan_key)
            exp_date, _ = get_plan_expiry_info(target_id)

            lines_admin = [
                f"Usuario: {{mono:{target_id}}}",
                f"Plan: {plan['badge']} {plan['display']}",
                f"Cuota: {plan['daily_label']}/día",
                f"Duración: {f'{days} días' if days > 0 else 'Permanente'}",
            ]
            if exp_date:
                lines_admin.append(f"Vence: {exp_date}")
            lines_admin.append("")
            lines_admin.append("💾 Guardado correctamente")

            await query.message.edit_text(
                card("✅ ᴘʟᴀɴ ᴀꜱɪɢɴᴀᴅᴏ", lines_admin),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return
        if query.data == "admin:check":
            context.user_data["admin_state"] = {"step": "awaiting_check_user_id"}
            await query.message.edit_text(
                card("🔍 ᴄᴏɴꜱᴜʟᴛᴀʀ ᴜꜱᴜᴀʀɪᴏ", [
                    "Envía el ID numérico de Telegram",
                    "del usuario que deseas consultar.",
                    "",
                    "Verás su saldo, plan, cuota usada,",
                    "referidos y descargas realizadas.",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data.startswith("admin:users:"):
            page = 0
            try:
                page = int(query.data.split(":", 2)[2])
            except Exception:
                page = 0
            users_data = _load_json(USERS_DATA_FILE).get("users", {})
            user_list = sorted(users_data.items(), key=lambda x: x[1].get("user_id", 0))
            per_page = 6
            total_pages = max(1, (len(user_list) + per_page - 1) // per_page)
            page = max(0, min(page, total_pages - 1))
            current_slice = user_list[page * per_page:(page + 1) * per_page]

            lines = [f"👥 Total registrados: {len(user_list)}", f"📄 Página {page + 1}/{total_pages}", ""]
            for uid_str, u in current_slice:
                name = (u.get("first_name") or u.get("full_name") or "Usuario")[:14]
                plan_info = get_plan_info(get_user_plan(int(uid_str)))
                balance = u.get("balance", 0)
                lines.append(f"• {{mono:{uid_str}}} | {name}")
                lines.append(f"  {plan_info['badge']} {plan_info['display']} · {balance}$")

            nav_buttons = []
            if page > 0:
                nav_buttons.append(btn("⬅️ Anterior", callback_data=f"admin:users:{page - 1}"))
            if page + 1 < total_pages:
                nav_buttons.append(btn("Siguiente ➡️", callback_data=f"admin:users:{page + 1}"))

            rows = []
            if nav_buttons:
                rows.append(nav_buttons)
            rows.append([btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")])

            await query.message.edit_text(
                card("👥 ᴜꜱᴜᴀʀɪᴏꜱ ʀᴇɢɪꜱᴛʀᴀᴅᴏꜱ", lines),
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if query.data == "admin:user_history":
            context.user_data["admin_state"] = {"step": "awaiting_user_history_id"}
            await query.message.edit_text(
                card("🗂️ ʜɪꜱᴛᴏʀɪᴀʟ ᴅᴇ ᴜꜱᴜᴀʀɪᴏ", [
                    "Envía el ID numérico del usuario",
                    "para ver sus archivos subidos.",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:all_history_confirm":
            await query.message.edit_text(
                card("⚠️ ʙᴏʀʀᴀʀ ᴛᴏᴅᴏ ᴇʟ ʜɪꜱᴛᴏʀɪᴀʟ", [
                    "¿Estás seguro de vaciar el",
                    "historial global de todos los usuarios?",
                    "",
                    "Esta acción no se puede deshacer.",
                ]),
                reply_markup=InlineKeyboardMarkup([
                    [btn("✅ ꜱí, ʙᴏʀʀᴀʀ ᴛᴏᴅᴏ", callback_data="admin:all_history_yes")],
                    [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="admin:back")],
                ]),
            )
            return

        if query.data == "admin:all_history_yes":
            _save_json(HISTORY_DATA_FILE, {})
            schedule_data_backup(context.application, "vaciado total del historial por admin")
            await query.message.edit_text(
                card("✅ ʜɪꜱᴛᴏʀɪᴀʟ ᴠᴀᴄɪᴀᴅᴏ", [
                    "El historial global de todos los",
                    "usuarios fue eliminado correctamente.",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:broadcast":
            context.user_data["admin_state"] = {"step": "awaiting_broadcast_text"}
            await query.message.edit_text(
                card("📢 ᴅɪꜰᴜꜱɪóɴ ᴍᴀꜱɪᴠᴀ", [
                    "Escribe y envía el mensaje que",
                    "deseas transmitir a todos los",
                    "usuarios registrados en el bot.",
                    "",
                    "Podrás previsualizarlo y confirmarlo",
                    "antes de realizar el envío.",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:broadcast_send":
            b_text = context.user_data.get("admin_broadcast_text")
            if not b_text:
                await query.answer(sc("No hay mensaje para difundir"), show_alert=True)
                return
            context.user_data.pop("admin_broadcast_text", None)
            context.user_data.pop("admin_state", None)
            user_ids = registered_user_ids()
            sent_count = 0
            fail_count = 0
            await query.message.edit_text(
                card("📢 ᴇɴᴠɪᴀɴᴅᴏ ᴅɪꜰᴜꜱɪóɴ", [
                    f"Transmitiendo a {len(user_ids)} usuarios...",
                    "Por favor espera...",
                ])
            )
            for uid in user_ids:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"┎ 📣 <b>ᴍᴇɴѕᴀᴊᴇ ᴅᴇ ᴇʟ ᴀᴅᴍɪɴ\n┠─────────────────────\n┖</b>{html.escape(b_text)}\n\n{BOT_FOOTER}",
                        parse_mode="HTML",
                    )
                    sent_count += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    fail_count += 1
            await query.message.edit_text(
                card("✅ ᴅɪꜰᴜꜱɪóɴ ᴄᴏᴍᴘʟᴇᴛᴀᴅᴀ", [
                    f"👥 Total usuarios: {len(user_ids)}",
                    f"✅ Enviados: {sent_count}",
                    f"❌ Fallidos/Bloqueados: {fail_count}",
                ]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if query.data == "admin:report":
            users_data = _load_json(USERS_DATA_FILE).get("users", {})
            history_data = _load_json(HISTORY_DATA_FILE)
            plan_data = _load_json(PLAN_DATA_FILE)
            total_users = len(users_data)
            total_transfers = sum(len(h) for h in history_data.values() if isinstance(h, list))
            total_bytes = 0
            for u_hist in history_data.values():
                if isinstance(u_hist, list):
                    for entry in u_hist:
                        total_bytes += entry.get("size", 0)

            queue_manager: FairTaskQueue = context.application.bot_data.get("task_queue")
            act_count = queue_manager.get_global_active_count() if queue_manager else 0
            q_count = queue_manager.get_global_queued_count() if queue_manager else 0

            lines = [
                f"👥 Usuarios registrados: {total_users}",
                f"📦 Transferencias completadas: {total_transfers}",
                f"💾 Volumen total movido: {_size_label(total_bytes, 2)}",
                f"⚡ Tareas activas en vivo: {act_count}",
                f"⏳ Tareas en cola en vivo: {q_count}",
                f"💰 Recompensa referidos: {REFERRAL_REWARD}$",
                f"⚡ Límite concurrente bot: {MAX_CONCURRENT_UPLOADS}",
                "",
                "🛡️ Sistema 100% operativo y optimizado.",
            ]
            await query.message.edit_text(
                card("🧾 ʀᴇᴘᴏʀᴛᴇ ᴀᴄᴜᴍᴜʟᴀᴛɪᴠᴏ", lines),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        return

    if query.data.startswith("help:"):
        try:
            page = int(query.data.split(":", 1)[1])
            if page < 0 or page >= len(HELP_PAGES):
                raise ValueError
        except Exception:
            return
        await query.message.edit_text(help_page_text(page), reply_markup=help_keyboard(page))
        return

    if query.data == "my_quota":
        box = card("📊 ᴍɪ ᴄᴜᴏᴛᴀ", quota_lines(user.id))
        await query.message.edit_text(
            f"{box}\n\n{BOT_FOOTER}",
            reply_markup=home_keyboard(),
        )
        return

    if query.data == "downloads":
        await query.message.edit_text(download_menu_text(), reply_markup=download_menu_keyboard())
        return

    if query.data in {"download:telegram", "download:url"}:
        source = query.data.split(":", 1)[1]
        await query.message.edit_text(download_prompt_text(source), reply_markup=download_prompt_keyboard())
        return

    if query.data == "open_queue":
        manager: FairTaskQueue = context.application.bot_data["task_queue"]
        text, markup = render_queue_view(user.id, manager)
        await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        return
    if query.data == "queue:paused":
        manager: FairTaskQueue = context.application.bot_data["task_queue"]
        paused_jobs = manager.get_local_paused(user.id)
        if not paused_jobs:
            await query.message.edit_text(
                card("⏸️ ᴛᴀʀᴇᴀꜱ ᴘᴀᴜꜱᴀᴅᴀꜱ", [
                    "No tienes tareas pausadas.",
                    "",
                    "Todas tus transferencias están",
                    "activas o ya fueron completadas.",
                ]),
                reply_markup=InlineKeyboardMarkup([
                    [btn("🔄 ᴠᴇʀ ᴍɪ ᴄᴏʟᴀ", callback_data="open_queue")],
                    [btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")],
                ]),
            )
            return

        lines = [
            f"Tienes {len(paused_jobs)} tarea(s) pausada(s).",
            "",
            "💡 Recuerda: las tareas pausadas NO",
            "ocupan cola ni bloquean tus descargas.",
            "",
        ]
        rows = []
        for i, j in enumerate(paused_jobs[:8], 1):
            name = (j.filename or j.source_url or "Tarea")[:18]
            size_str = _size_label(j.size, 1) if j.size else "Tamaño variable"
            lines.append(f"{i}. ⏸️ {name} ({size_str})")
            rows.append([
                btn(f"▶️ Reanudar {i}", callback_data=f"j:{j.task_id}:retry"),
                btn(f"ℹ️ Info", callback_data=f"j:{j.task_id}:open"),
                btn(f"🗑️ Borrar", callback_data=f"j:{j.task_id}:delete"),
            ])

        rows.append([
            btn("▶️ ʀᴇᴀɴᴜᴅᴀʀ ᴛᴏᴅᴀꜱ", callback_data="queue:resume_all"),
            btn("🗑️ ʙᴏʀʀᴀʀ ᴛᴏᴅᴀꜱ", callback_data="queue:clear_paused"),
        ])
        rows.append([
            btn("⬅️ ᴠᴏʟᴠᴇʀ ᴀ ᴍɪ ᴄᴏʟᴀ", callback_data="open_queue"),
            btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home"),
        ])

        box = card("⏸️ ᴛᴀʀᴇᴀꜱ ᴘᴀᴜꜱᴀᴅᴀꜱ", lines)
        await query.message.edit_text(
            f"{box}\n\n{BOT_FOOTER}",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        return

    if query.data == "queue:resume_all":
        manager: FairTaskQueue = context.application.bot_data["task_queue"]
        paused_jobs = manager.get_local_paused(user.id)
        count = 0
        for j in paused_jobs:
            await manager.requeue(j)
            count += 1
        await query.answer(sc(f"Reanudadas {count} tareas"))
        text_q, markup_q = render_queue_view(user.id, manager)
        await query.message.edit_text(text_q, reply_markup=markup_q, disable_web_page_preview=True)
        return

    if query.data == "queue:clear_paused":
        manager: FairTaskQueue = context.application.bot_data["task_queue"]
        paused_jobs = manager.get_local_paused(user.id)
        count = 0
        for j in paused_jobs:
            deleted = await manager.delete(j.task_id, user.id)
            if deleted:
                if deleted.temp_path:
                    Path(deleted.temp_path).unlink(missing_ok=True)
                for path in deleted.part_paths:
                    Path(path).unlink(missing_ok=True)
            count += 1
        await query.answer(sc(f"Eliminadas {count} tareas pausadas"))
        text_q, markup_q = render_queue_view(user.id, manager)
        await query.message.edit_text(text_q, reply_markup=markup_q, disable_web_page_preview=True)
        return

    if query.data == "open_history":
        persistent = get_task_history(user.id, 10)
        if not persistent:
            await query.message.edit_text(
                card("☁️ ᴍɪ ɴᴜʙᴇ", ["No tienes historial", "todavía."]),
                reply_markup=home_keyboard(),
            )
            return
        lines = []
        for number, entry in enumerate(persistent, 1):
            try:
                dt = datetime.fromisoformat(entry["completed_at"]).strftime("%d/%m %H:%M")
            except Exception:
                dt = "—"
            name = (entry.get("filename") or "Archivo")[:20]
            lines.append(f"{number}. ✅ {name}")
            lines.append(f"   {dt} · {_size_label(entry.get('size', 0), 1)}")
        rows = []
        for number, entry in enumerate(persistent[:5], 1):
            name = (entry.get("filename") or "Archivo")[:18]
            urls = entry.get("urls", [])
            if urls:
                rows.append([btn(f"📎 {number}. {name}", callback_data=f"history:view:{number - 1}")])
        rows.append([btn("🗑️ ᴠᴀᴄɪᴀʀ ɴᴜʙᴇ", callback_data="history:delete_menu")])
        rows.append([btn("🏠 ɪɴɪᴄɪᴏ", callback_data="home")])
        box = card("☁️ ᴍɪ ɴᴜʙᴇ", lines)
        await query.message.edit_text(
            f"{box}\n\n{BOT_FOOTER}",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
        return

    if query.data.startswith("history:view:"):
        try:
            index = int(query.data.rsplit(":", 1)[1])
            entry = get_task_history(user.id, 50)[index]
        except Exception:
            await query.answer(sc("Ese historial ya no existe"), show_alert=True)
            return
        await query.message.edit_text(
            transfer_complete_text(
                filename=entry.get("filename", "Archivo"),
                size=entry.get("size", 0),
                parts=entry.get("parts", 1),
                duration=entry.get("duration"),
                expires_at=entry.get("expires_at"),
            ),
            reply_markup=history_detail_keyboard(entry, index),
            disable_web_page_preview=True,
        )
        return

    if query.data.startswith("history:cloud_delete:"):
        try:
            index = int(query.data.rsplit(":", 1)[1])
            entry = get_task_history(user.id, 50)[index]
        except Exception:
            await query.answer(sc("Ese historial ya no existe"), show_alert=True)
            return
        urls = entry.get("urls", []) if isinstance(entry.get("urls"), list) else []
        await asyncio.gather(*(asyncio.to_thread(delete_from_todus_s3, url) for url in urls), return_exceptions=True)
        delete_task_history_entry(user.id, index)
        schedule_data_backup(context.application, "borrado de archivo")
        await query.message.edit_text(
            card("✅ ᴀʀᴄʜɪᴠᴏ ʙᴏʀʀᴀᴅᴏ", [
                "El archivo y su registro",
                "fueron eliminados.",
            ]),
            reply_markup=home_keyboard(),
        )
        return

    if query.data == "history:delete_menu":
        entries = get_task_history(user.id, 10)
        if not entries:
            await query.message.edit_text(
                card("🗑️ ʙᴏʀʀᴀʀ ʜɪꜱᴛᴏʀɪᴀʟ", ["No hay registros", "para eliminar."]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴍɪ ɴᴜʙᴇ ☁️", callback_data="open_history")]]),
            )
            return
        lines = ["Selecciona qué registro", "quieres eliminar:", ""]
        rows = []
        for number, entry in enumerate(entries, 1):
            name = (entry.get("filename") or "Archivo")[:24]
            lines.append(f"{number}. {name}")
            rows.append([btn(f"🗑️ ᴇʟɪᴍɪɴᴀʀ {number}", callback_data=f"history:delete:{number - 1}")])
        rows.append([btn("🧹 ʙᴏʀʀᴀʀ ᴛᴏᴅᴏ ᴇʟ ʜɪꜱᴛᴏʀɪᴀʟ", callback_data="history:clear:confirm")])
        rows.append([btn("⬅️ ᴍɪ ɴᴜʙᴇ ☁️", callback_data="open_history")])
        await query.message.edit_text(
            card("🗑️ ʙᴏʀʀᴀʀ ʜɪꜱᴛᴏʀɪᴀʟ", lines),
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if query.data.startswith("history:delete:"):
        try:
            index = int(query.data.rsplit(":", 1)[1])
        except Exception:
            return
        entries = get_task_history(user.id, 50)
        if index < 0 or index >= len(entries):
            return
        await delete_history_entry_cloud(entries[index])
        delete_task_history_entry(user.id, index)
        schedule_data_backup(context.application, "borrado de historial")
        await query.answer(sc("Historial eliminado"))
        await query.message.edit_text(
            card("☁️ ᴍɪ ɴᴜʙᴇ", ["Registro eliminado con éxito."]),
            reply_markup=home_keyboard(),
        )
        return

    if query.data == "history:clear:confirm":
        await query.message.edit_text(
            card("⚠️ ᴄᴏɴꜰɪʀᴍᴀʀ", [
                "¿Borrar todo el historial?",
                "",
                "Se borrarán los registros",
                "y también sus archivos",
                "guardados en ToDus.",
            ]),
            reply_markup=InlineKeyboardMarkup([
                [btn("✅ ʙᴏʀʀᴀʀ ᴛᴏᴅᴏ", callback_data="history:clear:yes")],
                [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="history:delete_menu")],
            ]),
        )
        return

    if query.data == "history:clear:yes":
        entries = get_task_history(user.id, 50)
        await asyncio.gather(*(delete_history_entry_cloud(entry) for entry in entries), return_exceptions=True)
        clear_task_history(user.id)
        schedule_data_backup(context.application, "borrado total del historial")
        await query.message.edit_text(
            card("✅ ʜɪꜱᴛᴏʀɪᴀʟ ʙᴏʀʀᴀᴅᴏ", ["El historial ha sido borrado con éxito."]),
            reply_markup=home_keyboard(),
        )
        return

    if query.data.startswith("j:"):
        try:
            _, task_id, action = query.data.split(":", 2)
        except ValueError:
            return
        manager: FairTaskQueue = context.application.bot_data["task_queue"]
        job = manager.jobs.get(task_id)
        if not job or job.user_id != user.id:
            await query.answer(sc("Tarea no disponible"), show_alert=True)
            return
        if action == "open":
            await show_task(job, target=query.message)
        elif action == "generate_txt":
            if job.state != "done" or not job.part_urls:
                return
            job.txt_generating = True
            txt_path = None
            try:
                txt_name = link_txt_filename(job.filename)
                urls = [url for _, url in sorted(job.part_urls.items())]
                content = "\n".join(urls) + "\n"
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", dir=TMPDIR, delete=False) as handle:
                    txt_path = Path(handle.name)
                    handle.write(content)
                with txt_path.open("rb") as document:
                    await context.bot.send_document(
                        chat_id=job.chat_id,
                        document=document,
                        filename=txt_name,
                        caption=sc("┎ ✅ ᴛxᴛ ʟɪꜱᴛᴏ\n┠─────────────────────\n┠ ʏᴀ ᴇꜱᴛᴀ‌ ᴅɪꜱᴘᴏɴɪʙʟᴇ ᴇɴ ʟᴀ ɴᴜʙᴇ.\n┃\n┠ Tú Archivo está disponible\n┠ para comenzar la descarga\n┠ toca para abrir el txt\n┠ con el APK Download Free\n┃\n┖ descarga el archivo antes de que expire aveces Expira antes de tiempo estamos trabajando en ello"),
                    )
            except Exception:
                pass
            finally:
                job.txt_generating = False
                if txt_path:
                    txt_path.unlink(missing_ok=True)
        elif action == "cancel":
            cancelled = await manager.cancel(task_id, user.id)
            if cancelled:
                await _edit_task_status(job, task_detail_text(job))
        elif action == "retry":
            await manager.requeue(job)
            await _edit_task_status(job, card("🔄 ʀᴇᴀɴᴜᴅᴀɴᴅᴏ", ["Reanudando partes..."]))
        elif action == "links":
            await send_task_links(job, context.bot)
        elif action == "cloud_delete":
            urls = list(job.part_urls.items())
            await asyncio.gather(*(asyncio.to_thread(delete_from_todus_s3, url) for _, url in urls), return_exceptions=True)
            job.part_urls.clear()
            job.set_state("cancelled")
            delete_task_history_by_task_id(user.id, job.task_id)
            schedule_data_backup(context.application, "borrado de archivo")
            await query.message.edit_text(
                card("🗑️ ᴀʀᴄʜɪᴠᴏ ᴇʟɪᴍɪɴᴀᴅᴏ", [
                    "El archivo fue eliminado",
                    "correctamente de la nube.",
                ]),
                reply_markup=home_keyboard(),
            )
        elif action == "delete":
            deleted = await manager.delete(task_id, user.id)
            if deleted:
                if deleted.temp_path:
                    Path(deleted.temp_path).unlink(missing_ok=True)
                for path in deleted.part_paths:
                    Path(path).unlink(missing_ok=True)
                await query.message.delete()
        return

    if query.data == "support":
        context.user_data["awaiting_support"] = True
        await query.message.reply_text(
            card("💬 ꜱᴏᴘᴏʀᴛᴇ", [
                "Escribe tu mensaje y",
                "se lo enviaré directo",
                "al creador.",
            ]),
            reply_markup=contact_keyboard(),
        )
    elif query.data == "home":
        context.user_data.pop("admin_state", None)
        context.user_data.pop("awaiting_support", None)
        await query.message.edit_text(
            welcome_text(
                user.id,
                getattr(user, "full_name", "") or getattr(user, "first_name", ""),
                getattr(user, "username", None),
            ),
            reply_markup=main_keyboard(user.id),
        )


async def owner_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not is_owner(user.id):
        return
    if len(context.args) < 2:
        await message.reply_text(sc("Uso: /reply ID respuesta"))
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await message.reply_text(sc("El ID debe ser numérico."))
        return
    response = " ".join(context.args[1:])[:3500]
    try:
        await context.bot.send_message(
            chat_id=target,
            text=card("📩 ʀᴇꜱᴘᴜᴇꜱᴛᴀ ᴅᴇ ꜱᴏᴘᴏʀᴛᴇ", [response]),
        )
        await message.reply_text(sc("✅ Mensaje enviado."))
    except Exception:
        await message.reply_text(sc("❌ No se pudo enviar el mensaje."))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat:
        return
    if not await ensure_membership(update, context):
        return
    if chat.type != "private":
        return

    text = (message.text or "").strip()
    admin_state = context.user_data.get("admin_state")
    if admin_state and is_owner(user.id):
        step = admin_state.get("step")
        if step == "awaiting_balance_user_id":
            try:
                target_id = int(text)
                if target_id <= 0: raise ValueError
            except ValueError:
                await message.reply_text(sc("Envía un ID numérico positivo."))
                return
            context.user_data["admin_state"] = {"step": "awaiting_balance_amount", "target_id": target_id}
            await message.reply_text(
                card("💵 ᴍᴏɴᴛᴏ ᴅᴇ ꜱᴀʟᴅᴏ", [f"ID: {{mono:{target_id}}}", "Envía la cantidad en pesos:"]),
                reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
            )
            return

        if step == "awaiting_balance_amount":
            try:
                amount = int(text)
                if amount <= 0 or amount > 1_000_000: raise ValueError
            except ValueError:
                await message.reply_text(sc("Envía una cantidad entera válida."))
                return
            target_id = int(admin_state["target_id"])
            context.user_data["admin_state"] = {"step": "awaiting_balance_confirmation", "target_id": target_id, "amount": amount}
            await message.reply_text(
                card("⚠️ ᴄᴏɴꜰɪʀᴍᴀʀ ꜱᴀʟᴅᴏ", [f"ID: {{mono:{target_id}}}", f"Monto: {amount}$", "", "¿Confirmas la acreditación?"]),
                reply_markup=InlineKeyboardMarkup([
                    [btn("✅ ᴄᴏɴꜰɪʀᴍᴀʀ", callback_data=f"admin:confirm_balance:{target_id}:{amount}")],
                    [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="admin:back")],
                ]),
            )
            return

        if step == "awaiting_user_id":
            try:
                target_id = int(text)
                if target_id <= 0: raise ValueError
            except ValueError:
                await message.reply_text(card("❌ ᴇʀʀᴏʀ", ["Envía un ID numérico válido."]))
                return
            plan_key = admin_state["plan"]
            days = admin_state.get("days", 0)
            plan = get_plan_info(plan_key)
            lines = [
                f"Usuario: {{mono:{target_id}}}",
                f"Plan: {plan['badge']} {plan['display']}",
                f"Duración: {f'{days} días' if days > 0 else 'Permanente'}",
                f"Cuota: {plan['daily_label']}/día",
                "",
                "¿Confirmar asignación?",
            ]
            await message.reply_text(
                card("✅ ᴄᴏɴꜰɪʀᴍᴀʀ", lines),
                reply_markup=InlineKeyboardMarkup([
                    [btn("✅ ᴄᴏɴꜰɪʀᴍᴀʀ", callback_data=f"admin:confirm_plan:{plan_key}:{days}:{target_id}")],
                    [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="admin:back")],
                ]),
            )
            return

        if step == "awaiting_check_user_id":
            try:
                target_id = int(text)
                if target_id <= 0: raise ValueError
            except ValueError:
                await message.reply_text(sc("Envía un ID numérico válido."))
                return
            context.user_data.pop("admin_state", None)
            users_data = _load_json(USERS_DATA_FILE).get("users", {})
            u_info = users_data.get(str(target_id), {})
            plan_key = get_user_plan(target_id)
            plan = get_plan_info(plan_key)
            balance = u_info.get("balance", get_user_balance(target_id))
            usage = get_daily_usage(target_id)
            quota_limit = plan.get("daily_limit")
            quota_str = f"{_size_label(usage, 1)} / {_size_label(quota_limit, 0)}" if quota_limit else f"{_size_label(usage, 1)} / Ilimitado"
            history = get_task_history(target_id, 10)
            reg_date = u_info.get("registered_at", "—")
            if reg_date != "—":
                try: reg_date = datetime.fromisoformat(reg_date).strftime("%d/%m/%Y")
                except Exception: pass
            
            lines = [
                f"🆔 ID: {target_id}",
                f"👤 Nombre: {u_info.get('full_name') or u_info.get('first_name') or 'Desconocido'}",
                f"🔖 Alias: @{u_info.get('username') or 'sin alias'}",
                f"💳 Plan: {plan['badge']} {plan['display']}",
                f"💸 Saldo: {balance}$",
                f"📦 Cuota hoy: {quota_str}",
                f"📅 Registro: {reg_date}",
                f"🗂️ Transferencias: {len(history)}",
            ]
            await message.reply_text(
                card("🔍 ᴅᴀᴛᴏꜱ ᴅᴇʟ ᴜꜱᴜᴀʀɪᴏ", lines),
                reply_markup=InlineKeyboardMarkup([
                    [btn("💸 ᴅᴀʀ ꜱᴀʟᴅᴏ", callback_data=f"admin:balance"),
                     btn("⭐ ᴄᴀᴍʙɪᴀʀ ᴘʟᴀɴ", callback_data=f"admin:plan:vip_basic")],
                    [btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")],
                ]),
            )
            return

        if step == "awaiting_user_history_id":
            try:
                target_id = int(text)
                if target_id <= 0: raise ValueError
            except ValueError:
                await message.reply_text(sc("Envía un ID numérico válido."))
                return
            context.user_data.pop("admin_state", None)
            history = get_task_history(target_id, 10)
            if not history:
                await message.reply_text(
                    card("🗂️ ʜɪꜱᴛᴏʀɪᴀʟ", [f"El usuario {target_id} no tiene historial registrado."]),
                    reply_markup=InlineKeyboardMarkup([[btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")]]),
                )
                return
            lines = [f"Historial de {target_id}:", ""]
            rows = []
            for i, h in enumerate(history[:6], 1):
                name = (h.get("filename") or "Archivo")[:20]
                lines.append(f"{i}. {name} ({_size_label(h.get('size', 0), 1)})")
                urls = h.get("urls", [])
                if urls:
                    rows.append([btn(f"📎 Enlace {i}", url=urls[0])])
            rows.append([btn("⬅️ ᴘᴀɴᴇʟ ᴀᴅᴍɪɴ", callback_data="admin:back")])
            await message.reply_text(
                card("🗂️ ʜɪꜱᴛᴏʀɪᴀʟ ᴅᴇ ᴜꜱᴜᴀʀɪᴏ", lines),
                reply_markup=InlineKeyboardMarkup(rows),
            )
            return

        if step == "awaiting_broadcast_text":
            context.user_data["admin_broadcast_text"] = text
            context.user_data["admin_state"] = {"step": "confirm_broadcast"}
            users_count = len(registered_user_ids())
            preview = text[:200] + ("..." if len(text) > 200 else "")
            await message.reply_text(
                card("⚠️ ᴄᴏɴꜰɪʀᴍᴀʀ ᴅɪꜰᴜꜱɪóɴ", [
                    f"Destinatarios: {users_count} usuarios",
                    "",
                    "Mensaje:",
                    preview,
                    "",
                    "¿Proceder con el envío masivo?",
                ]),
                reply_markup=InlineKeyboardMarkup([
                    [btn("📢 ᴇɴᴠɪᴀʀ ᴀ ᴛᴏᴅᴏꜱ", callback_data="admin:broadcast_send")],
                    [btn("❌ ᴄᴀɴᴄᴇʟᴀʀ", callback_data="admin:back")],
                ]),
            )
            return

    if context.user_data.get("awaiting_support"):
        owner_id = OWNER_TELEGRAM_ID
        body = text[:3000]
        username = f"@{user.username}" if user.username else "(sin alias)"
        try:
            await context.bot.send_message(
                chat_id=owner_id,
                text=(
                    f"📩 Nuevo mensaje de soporte\n"
                    f"👤 De: {username}\n"
                    f"🆔 ID: <code>{user.id}</code>\n\n"
                    f"{body}\n\n"
                    f"👉 Responde con:\n<code>/reply {user.id} tu respuesta</code>"
                ),
                parse_mode="HTML",
            )
            context.user_data.pop("awaiting_support", None)
            await message.reply_text(
                card("✅ ᴇɴᴠɪᴀᴅᴏ", ["Tu mensaje ha sido", "enviado al admin."]),
                reply_markup=home_keyboard(),
            )
        except Exception:
            await message.reply_text(sc("No se pudo enviar."))
        return

    try:
        source_urls = extract_http_urls(text)
    except ValueError as exc:
        await message.reply_text(sc(str(exc)))
        return
    for source_url in source_urls:
        await enqueue_transfer(update, context, source_kind="url", source_url=source_url)


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_private_update(update):
        return
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if not message or not user or not chat:
        return
    if not await ensure_membership(update, context):
        return
    if chat.type != "private":
        return

    # Si el creador envía un archivo ZIP de respaldo, ofrecer restauración automática
    if is_owner(user.id) and message.document and (message.document.file_name or "").endswith(".zip"):
        layout = context.application.bot_data.get("telegram_backup_layout")
        if layout:
            try:
                temp_fd, temp_zip = tempfile.mkstemp(prefix="manual_restore_", suffix=".zip", dir=TMPDIR)
                os.close(temp_fd)
                file_obj = await message.document.get_file()
                await file_obj.download_to_drive(custom_path=temp_zip)

                restored = 0
                with zipfile.ZipFile(temp_zip, "r") as zf:
                    for member in zf.infolist():
                        if member.is_dir() or member.filename == "backup_manifest.json":
                            continue
                        filename = member.filename
                        if filename.startswith("telegram_auth/"):
                            dest = layout.auth_dir / filename.replace("telegram_auth/", "")
                        else:
                            dest = layout.data_dir / filename
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(member) as source, open(dest, "wb") as target:
                            shutil.copyfileobj(source, target)
                        restored += 1
                Path(temp_zip).unlink(missing_ok=True)
                await message.reply_text(
                    card("✅ ʀᴇꜱᴘᴀʟᴅᴏ ʀᴇꜱᴛᴀᴜʀᴀᴅᴏ", [
                        f"Archivos restaurados: {restored}",
                        "Tu base de datos ha sido",
                        "actualizada con éxito.",
                    ])
                )
                return
            except Exception as e:
                log.warning(f"Error procesando zip manual: {e}")

    size_hint = None
    for media_name in ("document", "video", "animation", "audio", "voice", "video_note"):
        media = getattr(message, media_name, None)
        if media:
            size_hint = getattr(media, "file_size", None)
            break
    if not size_hint and getattr(message, "photo", None):
        size_hint = getattr(message.photo[-1], "file_size", None)
    max_size = 4096 * MIB
    if size_hint and size_hint > max_size and not is_owner(user.id):
        await message.reply_text(sc(f"El archivo supera el límite de {_size_label(max_size, 0)}."))
        return
    if size_hint and not is_owner(user.id):
        ok, err_msg = check_quota(user.id, size_hint)
        if not ok:
            await message.reply_text(err_msg, reply_markup=quota_exhausted_keyboard())
            return
    await enqueue_transfer(update, context, source_kind="media")


def schedule_data_backup(application: Application, reason: str = "cambio de datos") -> None:
    backup_chat_id = configured_backup_chat_id()
    layout = application.bot_data.get("telegram_backup_layout")
    if not backup_chat_id or layout is None:
        return
    async def run() -> None:
        lock = application.bot_data.get("telegram_backup_lock") or asyncio.Lock()
        async with lock:
            try:
                await backup_to_telegram(
                    application.bot,
                    getattr(application.bot, "token", ""),
                    backup_chat_id,
                    layout,
                    logger=log,
                )
            except Exception:
                pass
    application.bot_data["telegram_backup_pending_task"] = asyncio.create_task(run())


async def post_init(application: Application) -> None:
    # Garantizar archivo de cookies de YouTube en disco
    try:
        from platform_downloads import get_youtube_cookies_path
        cpath = get_youtube_cookies_path()
        if cpath:
            os.environ["YTDLP_COOKIES_FILE"] = str(cpath)
            log.info(f"Cookies de YouTube cargadas desde: {cpath}")
    except Exception as ce:
        log.warning(f"No se pudo inicializar cookies: {ce}")

    backup_chat_id = configured_backup_chat_id()
    backup_layout = telegram_backup_layout()
    backup_layout.auth_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    application.bot_data["telegram_backup_layout"] = backup_layout
    application.bot_data["telegram_backup_lock"] = asyncio.Lock()
    log.info(f"Canal de respaldo configurado: {backup_chat_id}")

    # 🚀 RESTAURACIÓN AUTOMÁTICA AL MIGRAR DE SERVIDOR:
    # Si los archivos de usuarios o planes no existen todavía en el nuevo hosting,
    # el bot descarga automáticamente el respaldo de Telegram antes de empezar a operar.
    if backup_chat_id:
        has_local_data = False
        if Path(PLAN_DATA_FILE).exists() and Path(USERS_DATA_FILE).exists():
            try:
                ud = _load_json(USERS_DATA_FILE)
                if isinstance(ud, dict) and len(ud.get("users", {})) > 0:
                    has_local_data = True
            except Exception:
                has_local_data = False
        if not has_local_data:
            log.info("📢 No se detectó base de datos local: iniciando restauración automática de Telegram...")
            try:
                restored, b_count = await restore_from_telegram(
                    application.bot,
                    getattr(application.bot, "token", ""),
                    backup_chat_id,
                    backup_layout,
                    logger=log,
                )
                log.info(f"✨ Migración automática exitosa: {restored} archivos recuperados ({b_count} bytes)")
            except Exception as exc:
                log.warning(f"Aviso de restauración inicial: {exc}")

    identity = await application.bot.get_me()
    application.bot_data["bot_username"] = identity.username or "Downfree_jk_bot"
    application.bot_data["quota_reset_task"] = asyncio.create_task(quota_reset_notifier(application))
    await asyncio.to_thread(expire_cloud_files)
    application.bot_data["cloud_expiration_task"] = asyncio.create_task(cloud_expiration_monitor(application))
    log.info("Bot activo: @%s (%s)", identity.username, getattr(identity, "first_name", ""))

    # Iniciar respaldos periódicos automáticos cada 10 minutos
    if backup_chat_id:
        application.bot_data["telegram_backup_task"] = asyncio.create_task(
            periodic_backup(
                application.bot,
                getattr(application.bot, "token", ""),
                backup_chat_id,
                backup_layout,
                interval_seconds=max(30, int(os.getenv("TELEGRAM_BACKUP_INTERVAL_SECONDS", "300") or 300)),
                lock=application.bot_data["telegram_backup_lock"],
                logger=log,
            )
        )

    await application.bot.set_my_commands([
        BotCommand("start", sc("abrir menú")),
        BotCommand("descargas", sc("menú de descargas")),
        BotCommand("ayuda", sc("ver ayuda")),
        BotCommand("cola", sc("tareas en curso")),
        BotCommand("historial", sc("historial de descargas")),
        BotCommand("micuota", sc("ver mi plan y cuota")),
        BotCommand("id", sc("ver mi id numérico")),
        BotCommand("backup", sc("crear respaldo en Telegram")),
        BotCommand("restore", sc("restaurar datos desde respaldo")),
    ])

    if application.bot_data.get("task_queue"):
        application.bot_data["task_workers"] = [
            asyncio.create_task(task_worker(application)) for _ in range(MAX_CONCURRENT_UPLOADS)
        ]

    # MTProto es opcional; solo se inicia si ambas credenciales están configuradas.
    application.bot_data["mtproto_client"] = None
    runtime_api_id = int(os.getenv("TELEGRAM_API_ID", str(ID_API_TELEGRAM)) or 0)
    runtime_api_hash = os.getenv("TELEGRAM_API_HASH", TELEGRAM_API_HASH).strip()
    if not (runtime_api_id and runtime_api_hash):
        log.info("MTProto no configurado; los archivos dentro del límite de Bot API seguirán funcionando.")
    else:
        try:
            session_path = TELEGRAM_AUTH_DIR / "mtproto_bot.session"
            mtproto_client = TelegramClient(str(session_path), runtime_api_id, runtime_api_hash)
            await mtproto_client.start(bot_token=application.bot.token)
            application.bot_data["mtproto_client"] = mtproto_client
            application.bot_data["mtproto_message_cache"] = {}

            async def cache_media_update(event):
                if not getattr(event.message, "media", None):
                    return
                cache = application.bot_data["mtproto_message_cache"]
                cache[(event.chat_id, event.id)] = event.message
                if len(cache) > 128:
                    cache.pop(next(iter(cache)))

            mtproto_client.add_event_handler(cache_media_update, events.NewMessage)
            try:
                await mtproto_client.catch_up()
            except Exception:
                pass
            log.info("MTProto listo con API ID %s", runtime_api_id)
        except Exception as exc:
            log.warning("MTProto no iniciado: %s (el bot continuará operando vía Bot API)", exc)

async def post_shutdown(application: Application) -> None:
    for task_name in ("quota_reset_task", "cloud_expiration_task", "telegram_backup_task"):
        task = application.bot_data.get(task_name)
        if task:
            task.cancel()
    workers = application.bot_data.get("task_workers", [])
    for worker in workers:
        worker.cancel()
    mtproto = application.bot_data.get("mtproto_client")
    if mtproto and mtproto.is_connected():
        await mtproto.disconnect()


def main() -> None:
    token = TELEGRAM_BOT_TOKEN.strip()
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en el entorno")

    defaults = Defaults(parse_mode=ParseMode.HTML)
    application = (
        Application.builder()
        .token(token)
        .defaults(defaults)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    application.bot_data.update({
        "mtproto_client": None,
        "local_bot_api": False,
        "owner_id": OWNER_TELEGRAM_ID,
        "allowed_users": set(),
        "task_queue": FairTaskQueue(),
        "task_worker_count": MAX_CONCURRENT_UPLOADS,
        "per_user_task_limit": 25,
    })
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("descargas", downloads_command))
    application.add_handler(CommandHandler("ayuda", help_command))
    application.add_handler(CommandHandler("cola", queue_command))
    application.add_handler(CommandHandler("historial", history_command))
    application.add_handler(CommandHandler("micuota", my_quota_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("restore", restore_command))
    application.add_handler(CommandHandler("jkadmin", jkadmin_command))
    application.add_handler(CommandHandler("reply", owner_reply_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    media_filters = (
        filters.Document.ALL | filters.VIDEO | filters.AUDIO
        | filters.PHOTO | filters.ANIMATION | filters.VIDEO_NOTE | filters.VOICE
    )
    application.add_handler(MessageHandler(media_filters, handle_media))
    log.info("JK Bot ToDus completamente inicializado y listo para correr")
    application.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
