"""Notificação nativa do sistema operacional, sem dependências extras.

- Windows: toast nativo via PowerShell (WinRT). Clicar no toast abre o vídeo.
- macOS: `osascript` (Central de Notificações).
- Linux: `notify-send` (libnotify).
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
from xml.sax.saxutils import escape, quoteattr

log = logging.getLogger(__name__)

APP_NAME = "TikTok Repost Monitor"
# AppUserModelID do Windows PowerShell: permite exibir toasts sem registrar um app.
WINDOWS_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

WINDOWS_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($env:RM_TOAST_XML)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:RM_APP_ID).Show($toast)
"""


def windows_toast_xml(title: str, body: str, url: str | None) -> str:
    launch = f" activationType=\"protocol\" launch={quoteattr(url)}" if url else ""
    actions = (
        f"<actions><action content=\"Abrir vídeo\" activationType=\"protocol\" arguments={quoteattr(url)}/></actions>"
        if url else ""
    )
    return (
        f"<toast{launch}><visual><binding template=\"ToastGeneric\">"
        f"<text>{escape(title)}</text><text>{escape(body)}</text>"
        f"</binding></visual>{actions}<audio src=\"ms-winsoundevent:Notification.Default\"/></toast>"
    )


def build_command(title: str, body: str, url: str | None, system: str | None = None) -> tuple[list[str], dict[str, str]] | None:
    """Retorna (comando, variáveis de ambiente extras) para o SO, ou None se não suportado."""
    system = system or platform.system()
    if system == "Windows":
        exe = shutil.which("powershell.exe") or shutil.which("powershell") or "powershell.exe"
        env = {"RM_TOAST_XML": windows_toast_xml(title, body, url), "RM_APP_ID": WINDOWS_APP_ID}
        return [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", WINDOWS_SCRIPT], env
    if system == "Darwin":
        script = [
            "-e", "on run argv",
            "-e", 'display notification (item 2 of argv) with title (item 1 of argv) sound name "Glass"',
            "-e", "end run",
        ]
        return ["osascript", *script, title, body], {}
    if shutil.which("notify-send"):
        return ["notify-send", "-a", APP_NAME, "-u", "critical", title, body + (f"\n{url}" if url else "")], {}
    return None


def send_desktop_notification(title: str, body: str, url: str | None = None) -> bool:
    """Envia a notificação; retorna False (sem levantar) se não for possível."""
    command = build_command(title, body, url)
    if command is None:
        log.warning("Notificação nativa indisponível neste sistema (instale notify-send no Linux).")
        return False
    argv, extra_env = command
    try:
        result = subprocess.run(
            argv, env={**os.environ, **extra_env}, capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("Falha ao exibir notificação nativa: %s", exc)
        return False
    if result.returncode != 0:
        log.warning("Notificação nativa retornou %s: %s", result.returncode, (result.stderr or "").strip()[:300])
        return False
    return True
