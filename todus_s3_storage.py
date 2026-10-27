from __future__ import annotations

import mimetypes
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, parse_qsl, urlencode, urlsplit, urlunsplit

import requests

TODUS_S3_BASE_URL = "https://s3.todus.cu/stream"
CHUNK_SIZE = 64 * 1024  # 64 KB para flujo óptimo y estable con ToDus S3
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
mimetypes.add_type("application/vnd.android.package-archive", ".apk")


def check_todus_url_alive(url: str, *, timeout_seconds: int = 8) -> bool:
    """Verifica si el enlace en ToDus S3 sigue respondiendo activamente (detecta 404/410)."""
    headers = {
        "User-Agent": "JK-Telegram-Bot/1.0",
        "Range": "bytes=0-0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }
    try:
        resp = requests.head(url, headers=headers, timeout=timeout_seconds, allow_redirects=True)
        if resp.status_code in {200, 206}:
            return True
        if resp.status_code in {404, 410}:
            return False
        if resp.status_code == 405:
            resp_get = requests.get(url, headers=headers, timeout=timeout_seconds, stream=True, allow_redirects=True)
            status = resp_get.status_code
            resp_get.close()
            if status in {404, 410}:
                return False
            return status in {200, 206}
        return resp.status_code < 400
    except Exception:
        # En caso de timeout no asumir falsamente 404
        return True


class ToDusS3UploadError(RuntimeError):
    """La subida a ToDus S3 no pudo completarse."""


class ToDusS3UploadCancelled(ToDusS3UploadError):
    """La subida se canceló antes de completarse."""


def delete_from_todus_s3(url: str, *, timeout_seconds: int = 60, base_url: str = TODUS_S3_BASE_URL) -> None:
    """Elimina y verifica un objeto previamente subido por este bot."""
    if not url.startswith(base_url.rstrip("/") + "/"):
        raise ValueError("La URL no pertenece al almacenamiento ToDus configurado.")

    timeout = max(10, int(timeout_seconds))
    headers = {
        "User-Agent": "JK-Telegram-Bot/1.0",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }

    try:
        response = requests.delete(url, timeout=timeout, headers=headers)
    except requests.RequestException as exc:
        raise ToDusS3UploadError(f"No se pudo conectar con ToDus S3 ({type(exc).__name__}).") from exc

    if response.status_code not in {200, 204, 404}:
        raise ToDusS3UploadError(f"ToDus S3 respondió HTTP {response.status_code} al borrar.")

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["hard_delete_check"] = uuid.uuid4().hex
    verify_url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    last_status = None
    for attempt in range(3):
        try:
            check = requests.head(verify_url, timeout=min(timeout, 30), headers=headers, allow_redirects=True)
            last_status = check.status_code
            if check.status_code in {404, 410}:
                return
            if check.status_code == 405:
                check = requests.get(
                    verify_url,
                    timeout=min(timeout, 30),
                    headers={**headers, "Range": "bytes=0-0"},
                    stream=True,
                    allow_redirects=True,
                )
                last_status = check.status_code
                check.close()
                if last_status in {404, 410}:
                    return
            if last_status not in {404, 410}:
                if attempt < 2:
                    time.sleep(1 + attempt)
                    continue
                raise ToDusS3UploadError(
                    f"ToDus todavía sirve el objeto después de borrarlo (HTTP {last_status})."
                )
        except requests.RequestException as exc:
            if attempt == 2:
                raise ToDusS3UploadError(
                    f"No se pudo verificar el borrado en ToDus ({type(exc).__name__})."
                ) from exc
            time.sleep(1 + attempt)

    raise ToDusS3UploadError(f"No se pudo verificar el borrado en ToDus (HTTP {last_status}).")


def build_object_key(
    telegram_user_id: int,
    now: datetime | None = None,
    filename: str | None = None,
) -> str:
    if isinstance(telegram_user_id, bool) or int(telegram_user_id) <= 0:
        raise ValueError("El ID de Telegram debe ser un entero positivo.")

    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    folder_id = uuid.uuid4().hex[:6]
    file_id = uuid.uuid4().hex[:12]

    original_name = Path(filename or "download.bin").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", original_name).strip("._") or "download.bin"
    extension = Path(safe_name).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,16}", extension):
        extension = ".bin"
        safe_name = f"{Path(safe_name).stem or 'download'}{extension}"

    return (
        f"users/tg_{int(telegram_user_id)}/telegram/"
        f"{stamp}-{folder_id}/telegram_{file_id}_{safe_name}"
    )


def _content_disposition(filename: str) -> str:
    name = Path(filename).name or "download.bin"
    ascii_fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in {'"', "\\", ";"} else "_"
        for char in name
    ).strip() or "download.bin"
    encoded = quote(name, safe="")
    disposition = "attachment" if Path(name).suffix.lower() == ".apk" else "inline"
    return f'{disposition}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


class _ProgressStream:
    """Flujo que envía fragmentos a ToDus y reporta progreso."""

    def __init__(
        self,
        file_obj,
        total: int,
        *,
        on_progress=None,
        is_cancelled=None,
        deadline: float,
    ) -> None:
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
            raise ToDusS3UploadCancelled("Subida cancelada.")
        if time.monotonic() > self._deadline:
            raise ToDusS3UploadError("Se agotó el tiempo máximo de subida a ToDus S3.")

    def read(self, size: int = -1) -> bytes:
        self._check()
        chunk = self._file.read(CHUNK_SIZE if size is None or size < 0 else size)
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
            chunk = self.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    def __getattr__(self, name):
        return getattr(self._file, name)


def upload_to_todus_s3(
    local_path: str | Path | None = None,
    filename: str | None = None,
    telegram_user_id: int | None = None,
    *,
    path: str | Path | None = None,
    download_name: str | None = None,
    on_progress=None,
    timeout_seconds: int = 24 * 60 * 60,
    is_cancelled=None,
    base_url: str = TODUS_S3_BASE_URL,
) -> tuple[str, int]:
    """Sube un archivo a ToDus S3 mediante PUT público y retorna su URL y tamaño.
    Admite nombres posicionales o por palabra clave (local_path/path, filename/download_name).
    """
    actual_path_raw = local_path if local_path is not None else path
    if actual_path_raw is None:
        raise ValueError("Se debe proporcionar 'local_path' o 'path'.")
    actual_path = Path(actual_path_raw)
    if not actual_path.is_file():
        raise FileNotFoundError(f"Archivo no encontrado: {actual_path}")

    actual_filename = filename if filename is not None else (download_name or actual_path.name)
    if telegram_user_id is None:
        raise ValueError("Se debe proporcionar 'telegram_user_id'.")

    size = actual_path.stat().st_size
    key = build_object_key(int(telegram_user_id), filename=actual_filename)
    url = f"{base_url.rstrip('/')}/{quote(key, safe='/')}"
    content_type = mimetypes.guess_type(Path(actual_filename).name)[0] or "application/octet-stream"
    headers = {
        "Content-Type": content_type,
        "Content-Length": str(size),
        "Content-Disposition": _content_disposition(actual_filename),
        "User-Agent": "JK-Telegram-Bot/1.0",
    }
    timeout = max(30, int(timeout_seconds))
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    with requests.Session() as session:
        for attempt in range(MAX_RETRIES):
            if is_cancelled and is_cancelled():
                raise ToDusS3UploadCancelled("Subida cancelada.")
            try:
                with actual_path.open("rb") as file_obj:
                    body = _ProgressStream(
                        file_obj,
                        size,
                        on_progress=on_progress,
                        is_cancelled=is_cancelled,
                        deadline=deadline,
                    )
                    response = session.put(
                        url,
                        data=body,
                        headers=headers,
                        timeout=(30, timeout),
                    )
            except ToDusS3UploadCancelled:
                raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 < MAX_RETRIES and time.monotonic() < deadline:
                    time.sleep(min(RETRY_BACKOFF_SECONDS**attempt, 8))
                    continue
                raise ToDusS3UploadError(
                    f"No se pudo conectar con ToDus S3 ({type(exc).__name__})."
                ) from exc

            if response.status_code == 200:
                return url, size
            if response.status_code >= 500 and attempt + 1 < MAX_RETRIES:
                time.sleep(min(RETRY_BACKOFF_SECONDS**attempt, 8))
                continue
            raise ToDusS3UploadError(
                f"ToDus S3 respondió HTTP {response.status_code}."
            )

    if last_error:
        raise ToDusS3UploadError(
            f"No se pudo conectar con ToDus S3 ({type(last_error).__name__})."
        ) from last_error
    raise ToDusS3UploadError("No se pudo completar la subida a ToDus S3.")
