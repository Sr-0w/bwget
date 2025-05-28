#!/usr/bin/env python3
"""
bwget -- “Better Wget” in Python
--------------------------------

A tiny, single‑file replacement for the parts of GNU wget most people
actually use: downloading one HTTP/HTTPS resource with a pretty progress
bar, automatic filename selection, optional resume, TLS verification,
automatic retries, optional SHA‑256 verification, and proxy support
via CLI, config file, or environment variables.
"""

from __future__ import annotations

# ──────────────────────────────────────────
# absolutely-minimal imports for early bar
# ──────────────────────────────────────────
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
EARLY_PB = Progress(*cols, console=console, transient=True)
EARLY_PB.add_task("Initializing…", total=None, start=True)
EARLY_PB.start()

# ──────────────────────────────────────────
# rest of the “heavy” imports come afterwards
# ──────────────────────────────────────────
import argparse
import hashlib
import os
import platform
import re
import time
from pathlib import Path
from textwrap import shorten
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.exceptions import (
    ConnectionError, HTTPError, RequestException, Timeout, ChunkedEncodingError,
)
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TextColumn,
)
from rich.markup import escape


# --- TOML library import ---
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
VERSION = "0.3.4"  # new minor version for spinner integration

cfg = {
    "user_agent": f"bwget/{VERSION} (Python/{sys.version_info.major}.{sys.version_info.minor})",
    "max_retries": 3, "base_backoff": 1.0,
    "request_timeout": 15, "stream_timeout": 30,
    "chunk_size": 1 << 18, "hash_chunk_size": 1 << 20,
    "proxy_url_config": None, "final_proxies_dict": None,
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

[download]
chunk_size_kb = {cfg['chunk_size'] // 1024}
hash_chunk_size_mb = {cfg['hash_chunk_size'] // (1024 * 1024)}
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
                loaded_toml_config = tomllib.load(f) if tomllib_present else toml.load(open(config_path, "r", encoding="utf-8"))
        except Exception as e:
            console.print(f"[warning]Could not load/parse config {escape(str(config_path))}: {e}[/warning]", style="yellow")
    elif tomllib_present or toml_present:
        create_sample_config(config_path)

    net_conf, dl_conf = loaded_toml_config.get("network", {}), loaded_toml_config.get("download", {})
    cfg.update({
        "user_agent": net_conf.get("user_agent", cfg["user_agent"]),
        "max_retries": int(net_conf.get("max_retries", cfg["max_retries"])),
        "base_backoff": float(net_conf.get("base_backoff", cfg["base_backoff"])),
        "request_timeout": int(net_conf.get("request_timeout", cfg["request_timeout"])),
        "stream_timeout": int(net_conf.get("stream_timeout", cfg["stream_timeout"])),
        "proxy_url_config": net_conf.get("proxy"),
        "chunk_size": int(dl_conf.get("chunk_size_kb", cfg["chunk_size"] // 1024)) * 1024,
        "hash_chunk_size": int(dl_conf.get("hash_chunk_size_mb", cfg["hash_chunk_size"] // (1024*1024))) * 1024 * 1024,
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
            # The connection progress bar is now started earlier in download(),
            # so we simply open the stream here.
            r = requests.get(
                url,
                stream=True,
                headers=stream_headers,
                timeout=cfg["stream_timeout"],
                proxies=cfg["final_proxies_dict"],
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


def download(
    url: str,
    initial_out_path: Path,
    explicit_output_given: bool,
    resume: bool,
    expected_sha256: str | None,
) -> None:

    final_out_path, http_headers = initial_out_path, {"User-Agent": cfg["user_agent"]}

    # If the early placeholder bar is running, update its label
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
                # print human-readable resume point
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

            # Stop the early placeholder bar — real progress starts now
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
                    "Progress" if mode == "wb" else "Res",
                    total=total_prog,
                    completed=comp_prog,
                    start=(comp_prog < total_prog or not total_prog),
                )
                with final_out_path.open(mode) as f:
                    for chunk in r.iter_content(chunk_size=cfg["chunk_size"]):
                        if chunk:
                            if (not progress.tasks[task_id].started) and total_prog:
                                progress.start_task(task_id)
                            f.write(chunk)
                            dl_sess += len(chunk)
                            progress.update(task_id, advance=len(chunk))

            # ── post-download summary ─────────────────────────────────────────
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
        if placeholder_pb:
            placeholder_pb.stop()
        sys.exit(3)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main() -> None:
    global cfg

    load_and_apply_config()

    parser = argparse.ArgumentParser(
        prog="bwget",
        description=__doc__.splitlines()[2].strip(),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("url", help="HTTP(S) URL to fetch")
    parser.add_argument("-o", "--output", metavar="FILE",
                        help="explicit output filename/path")
    # Default is now to *resume* automatically.
    # Supplying -c / --continue will *disable* resuming and start fresh.
    parser.add_argument(
        "-c", "--cancel-resume",
        dest="resume",
        action="store_false",
        help="do NOT resume; start downloading from scratch",
    )
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="suppress non-error output (hides progress bar)")
    parser.add_argument("--sha256", metavar="HEXDIGEST",
                        help="expected SHA-256 (64 hex chars). "
                             "Auto-fetches <URL>.sha256 if not given.")
    parser.add_argument("--proxy", metavar="PROXY_URL",
                        help="HTTP/HTTPS proxy URL "
                             "(e.g., http://user:pass@host:port)")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {VERSION}")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    ns = parser.parse_args()

    global EARLY_PB
    if ns.quiet:
        if EARLY_PB:
            EARLY_PB.stop()
            EARLY_PB = None
        console.quiet = True

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

    req_hdrs     = {"User-Agent": cfg["user_agent"]}
    expected_sha = (ns.sha256.lower()
                    if ns.sha256 else fetch_remote_sha256(ns.url, req_hdrs))

    if ns.sha256 and (not expected_sha or len(expected_sha) != 64
                      or not all(c in "0123456789abcdefABCDEF" for c in expected_sha)):
        console.print("[red]⨯ Invalid SHA-256 provided (must be 64 hex chars).[/]")
        sys.exit(2)

    if expected_sha and len(expected_sha) != 64:
        console.print(f"[red]⨯ Fetched SHA-256 invalid (len {len(expected_sha)}).[/]")
        expected_sha = None

    initial_path = pick_initial_filename(ns.url, ns.output)
    download(
        ns.url,
        initial_path,
        ns.output is not None,
        ns.resume,
        expected_sha,
    )


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
