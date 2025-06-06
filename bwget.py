#!/usr/bin/env python3
"""
bwget -- “Better Wget” in Python
--------------------------------

A tiny, single‑file replacement for the parts of GNU wget most people
actually use: downloading one HTTP/HTTPS resource (or a single torrent)
with a pretty progress bar, automatic filename selection, optional resume,
TLS verification, automatic retries, optional SHA‑256 verification, and
proxy support via CLI, config file, or environment variables.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Minimal imports used for the early progress bar
# ---------------------------------------------------------------------------
import sys
from rich.console import Console
from rich.progress import (
    Progress, BarColumn, DownloadColumn, TransferSpeedColumn,
    TimeRemainingColumn, TextColumn
)

console = Console(highlight=False, style="default on default")

cols = [
    TextColumn("[deep_sky_blue1]{task.description}[/] {task.percentage:>6.2f}%"),
    BarColumn(bar_width=None),
    DownloadColumn(binary_units=True),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
]

# Display the early progress bar only when a download is likely to occur
show_early_bar = (
    len(sys.argv) > 1
    and not any(arg in {"-h", "--help", "--version"} for arg in sys.argv[1:])
)

EARLY_PB: Progress | None
if show_early_bar:
    EARLY_PB = Progress(*cols, console=console, transient=True)
    EARLY_PB.add_task("Initializing…", total=None, start=True)
    EARLY_PB.start()
else:
    EARLY_PB = None

# ---------------------------------------------------------------------------
# Remaining imports
# ---------------------------------------------------------------------------
import argparse
import hashlib
import os
import platform
import re
import time
import tempfile
from pathlib import Path
from textwrap import shorten
from urllib.parse import urlsplit, urlunsplit
import shutil

import requests
from requests.exceptions import (
    ConnectionError, HTTPError, RequestException, Timeout, ChunkedEncodingError,
)
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn,
)
from rich.markup import escape


# ---------------------------------------------------------------------------
# TOML library import
# ---------------------------------------------------------------------------
try:
    import tomllib
    tomllib_present = True
except ImportError:
    tomllib_present = False
    try:
        import toml
        toml_present = True
    except ImportError:
        toml_present = False

# ---------------------------------------------------------------------------
# Version & Initial Configuration
# ---------------------------------------------------------------------------
VERSION = "0.4.0"

cfg = {
    "user_agent": f"bwget/{VERSION} (Python/{sys.version_info.major}.{sys.version_info.minor})",
    "max_retries": 3, "base_backoff": 1.0,
    "request_timeout": 15, "stream_timeout": 30,
    "chunk_size": 1 << 18, "hash_chunk_size": 1 << 20,
    "proxy_url_config": None, "final_proxies_dict": None,
    "verify_tls": True,
    "resume_default": True,
    "torrent_listen_interfaces": "0.0.0.0:6881-6891",
    "bandwidth_limit": 0,
    "torrent_max_seeds": 0,
}

TRANSIENT_STATUS = {500, 502, 503, 504}
TRANSIENT_EXCEPTIONS = (ConnectionError, Timeout, ChunkedEncodingError)

# ---------------------------------------------------------------------------
# Configuration File Handling
# ---------------------------------------------------------------------------

def get_config_file_path() -> Path:
    system = platform.system()
    if system == "Windows":
        base_path = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base_path = Path.home() / "Library" / "Application Support"
    else:
        base_path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_path / "bwget" / "config.toml"


def create_sample_config(config_path: Path):
    sample_config_content = f"""\
# bwget configuration file ({escape(str(config_path))})
# You can uncomment and modify these settings.

[network]
# proxy = "http://user:pass@yourproxy.example.com:8080"
user_agent = "{cfg['user_agent']}"
max_retries = {cfg['max_retries']}
base_backoff = {cfg['base_backoff']:.1f}
request_timeout = {cfg['request_timeout']}
    stream_timeout = {cfg['stream_timeout']}
    verify_tls = true

[download]
    chunk_size_kb = {cfg['chunk_size'] // 1024}
    hash_chunk_size_mb = {cfg['hash_chunk_size'] // (1024 * 1024)}
    resume_default = true
    bandwidth_limit_kbps = 0

[torrent]
    listen_interfaces = "{cfg['torrent_listen_interfaces']}"
    max_seeds = 0
"""
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(sample_config_content)
        console.print(f"[info]Created sample config: [bold cyan]{escape(str(config_path))}[/bold cyan][/info]")
        console.print("[info]Edit it for preferences (e.g., proxy).[/info]")
    except Exception as e:
        console.print(f"[warning]Could not create sample config {escape(str(config_path))}: {e}[/warning]", style="yellow")


def load_and_apply_config():
    global cfg
    config_path = get_config_file_path()
    loaded_toml_config = {}

    if not (tomllib_present or toml_present):
        console.print("[warning]No TOML library (tomllib/toml) found. Skipping config file.[/warning]", style="yellow")
        if not config_path.exists():
            create_sample_config(config_path)
        return

    if config_path.exists():
        try:
            with open(config_path, "rb") as f:
                if tomllib_present:
                    loaded_toml_config = tomllib.load(f)
                else:
                    loaded_toml_config = toml.load(f)
        except Exception as e:
            console.print(
                f"[warning]Could not load/parse config {escape(str(config_path))}: {e}[/warning]",
                style="yellow",
            )
    elif tomllib_present or toml_present:
        create_sample_config(config_path)

    net_conf = loaded_toml_config.get("network", {})
    dl_conf = loaded_toml_config.get("download", {})
    torrent_conf = loaded_toml_config.get("torrent", {})
    cfg.update({
        "user_agent": net_conf.get("user_agent", cfg["user_agent"]),
        "max_retries": int(net_conf.get("max_retries", cfg["max_retries"])),
        "base_backoff": float(net_conf.get("base_backoff", cfg["base_backoff"])),
        "request_timeout": int(net_conf.get("request_timeout", cfg["request_timeout"])),
        "stream_timeout": int(net_conf.get("stream_timeout", cfg["stream_timeout"])),
        "proxy_url_config": net_conf.get("proxy"),
        "verify_tls": bool(net_conf.get("verify_tls", cfg["verify_tls"])),
        "chunk_size": int(dl_conf.get("chunk_size_kb", cfg["chunk_size"] // 1024)) * 1024,
        "hash_chunk_size": int(dl_conf.get("hash_chunk_size_mb", cfg["hash_chunk_size"] // (1024*1024))) * 1024 * 1024,
        "resume_default": bool(dl_conf.get("resume_default", cfg["resume_default"])),
        "bandwidth_limit": int(dl_conf.get("bandwidth_limit_kbps", cfg["bandwidth_limit"] // 1024)) * 1024,
        "torrent_listen_interfaces": torrent_conf.get("listen_interfaces", cfg["torrent_listen_interfaces"]),
        "torrent_max_seeds": int(torrent_conf.get("max_seeds", cfg["torrent_max_seeds"])),
    })

# ---------------------------------------------------------------------------
# Helpers & Core Logic
# ---------------------------------------------------------------------------

def _parse_content_disposition(cd_header: str | None) -> str | None:
    if not cd_header:
        return None
    match = re.search(r'filename="?([^";]+)"?', cd_header, re.IGNORECASE)
    return Path(match.group(1).strip()).name if match else None


def pick_initial_filename(url: str, explicit_path_str: str | None) -> Path:
    if explicit_path_str:
        return Path(explicit_path_str).expanduser()
    return Path(Path(urlsplit(url).path.rstrip("/")).name or "index.html")


def request_head(url: str, headers: dict) -> requests.Response | None:
    try:
        return requests.head(
            url,
            allow_redirects=True,
            timeout=cfg["request_timeout"],
            headers=headers,
            proxies=cfg["final_proxies_dict"],
            verify=cfg["verify_tls"],
        )
    except RequestException as e:
        console.print(f"[yellow]ⓘ HEAD request failed for {shorten(url, 70)}: {e}[/]", highlight=True)
        return None


def fetch_remote_sha256(url: str, headers: dict) -> str | None:
    sha_url = url + ".sha256"
    try:
        r = requests.get(
            sha_url,
            timeout=cfg["request_timeout"],
            headers=headers,
            proxies=cfg["final_proxies_dict"],
            verify=cfg["verify_tls"],
        )
        r.raise_for_status()
        first_line = r.text.strip().splitlines()[0]
        token = first_line.split()[0]
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            console.print(f"[cyan]✓[/] Loaded checksum from {shorten(sha_url, 60)}")
            return token.lower()
        console.print(f"[yellow]⚠ Invalid checksum format in {shorten(sha_url, 60)}[/]")
    except RequestException:
        pass
    return None


def _open_stream(url: str, stream_headers: dict[str, str]) -> requests.Response:
    """Open the HTTP stream with a spinner shown until the first byte arrives."""

    attempt, backoff, max_r = 0, cfg["base_backoff"], cfg["max_retries"]

    while True:
        attempt += 1
        try:
            # Connection progress starts earlier in download(); just open here
            r = requests.get(
                url,
                stream=True,
                headers=stream_headers,
                timeout=cfg["stream_timeout"],
                proxies=cfg["final_proxies_dict"],
                verify=cfg["verify_tls"],
            )
            r.raise_for_status()
            return r

        except HTTPError as exc:
            if exc.response.status_code in TRANSIENT_STATUS and attempt < max_r:
                console.print(
                    f"[yellow]⚠ Att {attempt}/{max_r} (HTTP {exc.response.status_code}):[/] {exc.response.reason}. Retry in {backoff:.1f}s…"
                )
                time.sleep(backoff)
                backoff *= 2
            else:
                raise
        except TRANSIENT_EXCEPTIONS as exc:
            if attempt >= max_r:
                raise
            console.print(
                f"[yellow]⚠ Att {attempt}/{max_r}:[/] {type(exc).__name__}. Retry in {backoff:.1f}s…"
            )
            time.sleep(backoff)
            backoff *= 2


def verify_sha256_with_progress(file_path: Path, expected_digest: str):
    global EARLY_PB
    if EARLY_PB is not None:
        EARLY_PB.stop()
        EARLY_PB = None
    console.print(f"[cyan]Verifying SHA-256 for [bold]{escape(file_path.name)}[/]...[/]")
    sha, file_size = hashlib.sha256(), file_path.stat().st_size
    with file_path.open("rb") as f, Progress(
        TextColumn("[deep_sky_blue1]{task.description}[/] {task.percentage:>6.2f}%"),
        BarColumn(bar_width=None),
        DownloadColumn(binary_units=True),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("Hashing", total=file_size)
        for block in iter(lambda: f.read(cfg["hash_chunk_size"]), b""):
            sha.update(block)
            progress.update(task_id, advance=len(block))
    file_digest = sha.hexdigest()
    if file_digest == expected_digest:
        console.print("[green]✓ Checksum OK[/]")
    else:
        console.print(
            f"[red]⨯ SHA‑256 mismatch![/]\n  Expected: {expected_digest}\n  Actual:   {file_digest}"
        )
        try:
            file_path.unlink()
            console.print(
                f"[yellow]ⓘ Deleted mismatched file: {escape(str(file_path))}[/]"
            )
        except OSError as e:
            console.print(
                f"[red]⨯ Could not delete mismatched file {escape(str(file_path))}: {e}[/]"
            )
        sys.exit(2)


def ensure_disk_space(path: Path, required_bytes: int) -> None:
    """Abort if ``path``'s filesystem lacks ``required_bytes`` free."""
    try:
        usage = shutil.disk_usage(path.parent)
        if usage.free < required_bytes:
            need_mb = required_bytes / (1024 ** 2)
            free_mb = usage.free / (1024 ** 2)
            console.print(
                f"[red]⨯ Not enough disk space for {escape(str(path))}. "
                f"Need {need_mb:.1f} MiB, available {free_mb:.1f} MiB[/]"
            )
            sys.exit(1)
    except Exception as e:
        console.print(f"[yellow]⚠ Could not check disk space: {e}[/]")


def is_torrent(url: str) -> bool:
    return url.startswith("magnet:") or url.lower().endswith(".torrent")


def looks_like_url(s: str) -> bool:
    """Return True if ``s`` appears to be a URL we can handle."""
    parsed = urlsplit(s)
    if parsed.scheme in {"http", "https", "ftp"}:
        return bool(parsed.netloc)
    if parsed.scheme == "magnet":
        return True
    return False


def download_torrent(url: str, out_dir: Path, expected_sha256: str | None = None) -> None:
    """Download a single torrent or magnet link without seeding.

    If ``expected_sha256`` is provided and the torrent contains exactly one
    file, its SHA‑256 will be verified after the download completes.
    """
    global EARLY_PB
    if EARLY_PB is not None:
        for task in EARLY_PB.tasks:
            EARLY_PB.update(task.id, description="Connecting…")

    try:
        import libtorrent as lt
    except ImportError:
        console.print(
            "[red]⨯ libtorrent module is required for torrent downloads.[/]")
        sys.exit(3)

    ses = lt.session()
    if hasattr(lt, "settings_pack"):
        pack = lt.settings_pack()
        pack.listen_interfaces = cfg["torrent_listen_interfaces"]
        ses.apply_settings(pack)

    use_modern_api = hasattr(lt, "add_torrent_params")
    params = lt.add_torrent_params() if use_modern_api else {"save_path": str(out_dir)}
    if use_modern_api:
        params.save_path = str(out_dir)
    if cfg["torrent_max_seeds"] > 0:
        if use_modern_api and hasattr(params, "max_connections"):
            params.max_connections = cfg["torrent_max_seeds"]
        elif not use_modern_api:
            params["max_connections"] = cfg["torrent_max_seeds"]

    if url.startswith("magnet:"):
        if use_modern_api and hasattr(lt, "add_magnet_uri"):
            try:
                handle = lt.add_magnet_uri(ses, url, params)
            except Exception:
                if hasattr(lt, "parse_magnet_uri"):
                    params = lt.parse_magnet_uri(url)
                    params.save_path = str(out_dir)
                    handle = ses.add_torrent(params)
                else:
                    params = {"save_path": str(out_dir), "url": url}
                    handle = ses.add_torrent(params)
        else:
            if use_modern_api and hasattr(lt, "parse_magnet_uri"):
                params = lt.parse_magnet_uri(url)
                params.save_path = str(out_dir)
            else:
                params = {"save_path": str(out_dir), "url": url}
            handle = ses.add_torrent(params)
    else:
        r = requests.get(
            url,
            timeout=cfg["request_timeout"],
            headers={"User-Agent": cfg["user_agent"]},
            proxies=cfg["final_proxies_dict"],
            verify=cfg["verify_tls"],
        )
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(r.content)
            temp_path = tf.name
        info = lt.torrent_info(temp_path)
        os.unlink(temp_path)
        if use_modern_api:
            params.ti = info
        else:
            params["ti"] = info
        handle = ses.add_torrent(params)

    if cfg["torrent_max_seeds"] > 0 and hasattr(handle, "set_max_connections"):
        try:
            handle.set_max_connections(cfg["torrent_max_seeds"])
        except Exception:
            pass

    if EARLY_PB is not None:
        for task in EARLY_PB.tasks:
            EARLY_PB.update(task.id, description="Fetching metadata…")

    status = handle.status()
    torrent_name = status.name or getattr(handle, "name", lambda: "torrent")()
    console.print(
        f"[cyan]Downloading [bold]{escape(torrent_name)}[/]…[/]"
    )

    # has_metadata() is deprecated in modern libtorrent; use torrent_status
    while not handle.status().has_metadata:
        time.sleep(0.5)

    info = handle.torrent_file() if hasattr(handle, "torrent_file") else handle.get_torrent_info()
    total_bytes = info.total_size()
    status = handle.status()

    if EARLY_PB is not None:
        EARLY_PB.stop()
        EARLY_PB = None

    cols = [
        TextColumn("[green]{task.description}[/] [orange1]{task.percentage:>6.2f}%[/]"),
        BarColumn(None),
        DownloadColumn(True),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        TextColumn("[orange1]{task.fields[seeds]}/{task.fields[peers]} peers[/]"),
    ]

    with Progress(*cols, console=console, transient=True) as progress:
        task_id = progress.add_task("Progress", total=total_bytes, seeds=status.num_seeds, peers=status.num_peers, start=True)
        while not handle.status().is_seeding:
            s = handle.status()
            progress.update(task_id, completed=s.total_wanted_done, seeds=s.num_seeds, peers=s.num_peers)
            time.sleep(0.5)
        progress.update(task_id, completed=total_bytes)

    console.print("[green]✔ Torrent download complete[/]")

    if expected_sha256:
        try:
            info = handle.torrent_file() if hasattr(handle, "torrent_file") else handle.get_torrent_info()
            files = info.files()
            num_files = files.num_files() if hasattr(files, "num_files") else files.num_files
            if num_files == 1:
                rel_path = files.file_path(0)
                # ``torrent_handle.save_path()`` was deprecated in libtorrent
                # 2.0. Instead of conditionally calling this potentially
                # deprecated method, always use the value from
                # ``torrent_status.save_path`` which is supported across
                # versions and avoids the warning.
                save_root = Path(handle.status().save_path)
                file_path = save_root / rel_path
                if file_path.is_file():
                    verify_sha256_with_progress(file_path, expected_sha256)
                else:
                    console.print(
                        f"[yellow]⚠ Expected file {escape(str(file_path))} not found for checksum.[/]")
            else:
                console.print("[yellow]⚠ Cannot verify SHA-256 for multi-file torrent.[/]")
        except Exception as e:
            console.print(f"[yellow]⚠ SHA-256 verification skipped: {e}[/]")

    ses.remove_torrent(handle)


def download(
    url: str,
    initial_out_path: Path,
    explicit_output_given: bool,
    resume: bool,
    expected_sha256: str | None,
) -> None:

    final_out_path, http_headers = initial_out_path, {"User-Agent": cfg["user_agent"]}

    # Update placeholder progress bar while connecting
    global EARLY_PB
    if EARLY_PB is not None:
        for task in EARLY_PB.tasks:
            EARLY_PB.update(task.id, description="Connecting…")
    mode, downloaded_initial_size, original_total_size, server_supports_resume = (
        "wb",
        0,
        0,
        False,
    )

    head_resp = request_head(url, headers=http_headers)
    if head_resp:
        original_total_size = int(head_resp.headers.get("Content-Length", 0))
        server_supports_resume = "bytes" in head_resp.headers.get("Accept-Ranges", "").lower()
        if not explicit_output_given and (
            cd_fn := _parse_content_disposition(head_resp.headers.get("content-disposition"))
        ):
            final_out_path = initial_out_path.parent / cd_fn
            console.print(
                f"[cyan]ⓘ Filename (HEAD): [bold]{escape(final_out_path.name)}[/][/]"
            )

    if resume and final_out_path.exists():
        downloaded_initial_size = final_out_path.stat().st_size
        if downloaded_initial_size > 0:
            if original_total_size and downloaded_initial_size == original_total_size:
                console.print(
                    f"[green]✔[/] File [bold]{escape(final_out_path.name)}[/] already downloaded."
                )
                if expected_sha256:
                    verify_sha256_with_progress(final_out_path, expected_sha256)
                return
            elif original_total_size and downloaded_initial_size > original_total_size:
                console.print(
                    f"[yellow]⚠ Local [bold]{escape(final_out_path.name)}[/] larger. Starting fresh.[/]"
                )
                downloaded_initial_size = 0
            elif server_supports_resume or downloaded_initial_size > 0:
                http_headers["Range"] = f"bytes={downloaded_initial_size}-"
                mode = "ab"
                # Print human-readable resume point
                resumed_mb = downloaded_initial_size / (1024 ** 2)
                resumed_str = f"{resumed_mb:.1f} MB"
                total_str = ""
                if original_total_size:
                    total_gb = original_total_size / (1024 ** 3)
                    total_str = f" of {total_gb:.1f} GB"
                console.print(
                    f"[cyan]Resuming [bold]{escape(final_out_path.name)}[/] "
                    f"from {resumed_str}{total_str}[/]"
                )
            else:
                downloaded_initial_size = 0
        if downloaded_initial_size == 0:
            mode = "wb"

    try:
        with _open_stream(url, stream_headers=http_headers) as r:

            # Stop placeholder progress bar; real progress begins
            if EARLY_PB:
                EARLY_PB.stop()
                EARLY_PB = None
            if (
                not explicit_output_given
                and (final_out_path == initial_out_path or not head_resp)
                and (
                    cd_fn_get := _parse_content_disposition(
                        r.headers.get("content-disposition")
                    )
                )
            ):
                final_out_path = initial_out_path.parent / cd_fn_get
                console.print(
                    f"[cyan]ⓘ Filename (GET): [bold]{escape(final_out_path.name)}[/][/]"
                )

            resp_len = int(r.headers.get("Content-Length", 0))
            total_prog = (
                original_total_size
                or (downloaded_initial_size + resp_len if mode == "ab" else resp_len)
            )
            comp_prog = downloaded_initial_size if mode == "ab" else 0

            required_size = total_prog if mode == "wb" else max(0, total_prog - downloaded_initial_size)
            if required_size:
                ensure_disk_space(final_out_path, required_size)

            final_out_path.parent.mkdir(parents=True, exist_ok=True)
            host = urlsplit(r.url).hostname or urlsplit(url).hostname or "server"
            console.print(
                f"[cyan]Downloading from {host}[/] • Target: [bold]{escape(final_out_path.name)}[/]"
            )

            cols = [
                TextColumn("[green]{task.description}[/] [orange1]{task.percentage:>6.2f}%[/]"),
                BarColumn(None),
                DownloadColumn(True),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ]
            start_t, dl_sess = time.perf_counter(), 0
            with Progress(*cols, console=console, transient=True) as progress:
                task_id = progress.add_task(
                    "Progress" if mode == "wb" else "Progress",
                    total=total_prog,
                    completed=comp_prog,
                    start=(comp_prog < total_prog or not total_prog),
                )
                with final_out_path.open(mode) as f:
                    for chunk in r.iter_content(chunk_size=cfg["chunk_size"]):
                        if chunk:
                            if (not progress.tasks[task_id].started) and total_prog:
                                progress.start_task(task_id)
                            if cfg["bandwidth_limit"] > 0:
                                expected = dl_sess / cfg["bandwidth_limit"]
                                elapsed_bw = time.perf_counter() - start_t
                                if expected > elapsed_bw:
                                    time.sleep(expected - elapsed_bw)
                            f.write(chunk)
                            dl_sess += len(chunk)
                            progress.update(task_id, advance=len(chunk))

            # Post-download summary
            elapsed = time.perf_counter() - start_t or 1e-9
            f_size  = final_out_path.stat().st_size if final_out_path.exists() else 0
            mb      = f_size / (1 << 20)
            speed   = (dl_sess / (1 << 20)) / elapsed

            if expected_sha256:
                if f_size == 0:
                    console.print("[yellow]⚠ Cannot verify SHA-256 of empty file.[/]")
                else:
                    verify_sha256_with_progress(final_out_path, expected_sha256)

            out_dir  = final_out_path.parent.resolve()
            dir_uri  = out_dir.as_uri()
            console.print(
                f"[green]✔[/] Saved [bold]{escape(final_out_path.name)}[/] to "
                f"[link={dir_uri}][underline]{escape(str(out_dir))}[/underline][/link]"
            )
            console.print(
                f"[cyan]Total size:[/]\t{mb:,.2f} MiB\n"
                f"[cyan]Time (session):[/]\t{elapsed:,.1f} s\n"
                f"[yellow]Avg speed (session):[/]\t{speed:,.2f} MiB/s"
            )

    except KeyboardInterrupt:
        console.print("\n[red]⨯ Interrupted.[/]")
        if EARLY_PB:
            EARLY_PB.stop()
            EARLY_PB = None
        if final_out_path.exists():
            console.print(
                f"Partial file [bold]{escape(final_out_path.name)}[/] kept at "
                f"[underline]{escape(str(final_out_path))}[/underline]"
            )
        sys.exit(130)

    except RequestException as exc:
        console.print(f"[red]⨯ Download failed:[/] {exc}")
        if EARLY_PB:
            EARLY_PB.stop()
            EARLY_PB = None
        if mode == "wb" and final_out_path.exists() and downloaded_initial_size == 0:
            try:
                if final_out_path.stat().st_size > 0:
                    console.print(
                        f"[yellow]ⓘ Deleting incomplete: {escape(str(final_out_path))}[/]"
                    )
                    final_out_path.unlink()
                else:
                    final_out_path.unlink(missing_ok=True)
            except OSError as e:
                console.print(
                    f"[red]⨯ Could not delete: {escape(str(final_out_path))}: {e}[/]"
                )
        sys.exit(1)

    except Exception as e:
        console.print(f"[bold red]Unexpected error: {type(e).__name__}: {e}[/]")
        if EARLY_PB:
            EARLY_PB.stop()
            EARLY_PB = None
        sys.exit(3)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main() -> None:
    global cfg, EARLY_PB

    load_and_apply_config()

    parser = argparse.ArgumentParser(
        prog="bwget",
        description=__doc__.splitlines()[2].strip(),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("url", nargs="?", help="HTTP(S) URL to fetch")
    parser.add_argument(
        "-i", "--input", metavar="FILE",
        help="read URLs from FILE (one per line). "
             "If the positional URL looks like a local file, it is treated as such"
    )
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="explicit output filename/path")
    # Downloads resume by default; use -c/--cancel-resume to start fresh
    parser.add_argument(
        "-c", "--cancel-resume",
        dest="resume",
        action="store_false",
        default=cfg["resume_default"],
        help="do NOT resume; start downloading from scratch",
    )
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="suppress non-error output (hides progress bar)")
    parser.add_argument("--limit-rate", metavar="KBPS", type=int,
                        help="limit download bandwidth (KiB/s)")
    parser.add_argument("--sha256", metavar="HEXDIGEST",
                        help="expected SHA-256 (64 hex chars). "
                             "Auto-fetches <URL>.sha256 if not given.")

    parser.add_argument("--proxy", metavar="PROXY_URL",
                        help="HTTP/HTTPS proxy URL "
                             "(e.g., http://user:pass@host:port)")
    parser.add_argument("--max-seeds", metavar="N", type=int,
                        help="limit active torrent peers")
    parser.add_argument("-U", "--user-agent", metavar="UA",
                        help="override User-Agent header")
    parser.add_argument(
        "--no-check-certificate",
        action="store_true",
        help="disable TLS certificate verification (INSECURE)",
    )
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    ns = parser.parse_args()
    cfg["verify_tls"] = not ns.no_check_certificate

    if ns.quiet:
        if EARLY_PB:
            EARLY_PB.stop()
            EARLY_PB = None
        console.quiet = True

    if ns.user_agent:
        cfg["user_agent"] = ns.user_agent

    if ns.limit_rate is not None:
        cfg["bandwidth_limit"] = max(0, ns.limit_rate) * 1024

    if ns.max_seeds is not None:
        cfg["torrent_max_seeds"] = max(0, ns.max_seeds)


    proxy_url_str_to_use = ns.proxy or cfg["proxy_url_config"]
    if proxy_url_str_to_use:
        cfg["final_proxies_dict"] = {
            "http":  proxy_url_str_to_use,
            "https": proxy_url_str_to_use,
        }
        try:
            parsed_proxy = urlsplit(proxy_url_str_to_use)
            display_proxy = proxy_url_str_to_use
            if parsed_proxy.username or parsed_proxy.password:
                masked_netloc = (f"******:******@{parsed_proxy.hostname}"
                                 f"{':' + str(parsed_proxy.port) if parsed_proxy.port else ''}")
                display_proxy = urlunsplit(
                    list(parsed_proxy._replace(netloc=masked_netloc))
                )
        except Exception:
            console.print("[info]Using proxy (details suppressed).[/info]")
    else:
        cfg["final_proxies_dict"] = None

    req_hdrs = {"User-Agent": cfg["user_agent"]}

    urls: list[str] = []
    success_count = 0
    if ns.url:
        if looks_like_url(ns.url) or not Path(ns.url).is_file():
            urls.append(ns.url)
        else:
            try:
                with open(ns.url, "r", encoding="utf-8") as f:
                    for line in f:
                        url = line.strip()
                        if url and not url.startswith("#"):
                            urls.append(url)
            except Exception as e:
                console.print(
                    f"[red]⨯ Could not read input file {ns.url}: {e}[/]"
                )
                sys.exit(1)
    if ns.input:
        try:
            with open(ns.input, "r", encoding="utf-8") as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith("#"):
                        urls.append(url)
        except Exception as e:
            console.print(f"[red]⨯ Could not read input file {ns.input}: {e}[/]")
            sys.exit(1)

    if not urls:
        console.print("[red]⨯ No URL provided.[/]")
        sys.exit(1)

    total_urls = len(urls)

    for url in urls:
        expected_sha = ns.sha256.lower() if ns.sha256 else fetch_remote_sha256(url, req_hdrs)

        if ns.sha256 and (
            not expected_sha
            or len(expected_sha) != 64
            or not all(c in "0123456789abcdefABCDEF" for c in expected_sha)
        ):
            console.print("[red]⨯ Invalid SHA-256 provided (must be 64 hex chars). Skipping.[/]")
            continue

        if expected_sha and len(expected_sha) != 64:
            console.print(f"[red]⨯ Fetched SHA-256 invalid (len {len(expected_sha)}).[/]")
            expected_sha = None

        try:
            if is_torrent(url):
                out_dir = Path(ns.output).expanduser() if ns.output else Path('.')
                download_torrent(url, out_dir, expected_sha)
            else:
                initial_path = pick_initial_filename(url, ns.output)
                download(
                    url,
                    initial_path,
                    ns.output is not None,
                    ns.resume,
                    expected_sha,
                )
            success_count += 1
        except SystemExit as exc:
            if int(getattr(exc, "code", 1)) == 130:
                raise
            # Errors already reported; continue with next URL
            continue

    plural = "file" if total_urls == 1 else "files"
    console.print(f"[green]✔[/] Downloaded {success_count}/{total_urls} {plural}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled (main).[/]")
        sys.exit(130)
    except Exception as e:
        console.print(
            f"[bold red]Unhandled exception in main: {type(e).__name__}: {e}[/]"
        )
        sys.exit(3)
