# bwget

**Better Wget** in Python: a tiny, single-file replacement for the parts of GNU wget most people actually use.

![bwget demo](https://pouch.jumpshare.com/preview/P97VWVAAv80eYgIit58iPW7Z9p5B2Gii1s3TPaJwO_8I-1Ix-3go_5QyWkuWnjxU2A4Rb8yKhJS2MLfj-2Drjw5QoTvJ8_fU7PXfI7G3wVM)

---

## Features

* HTTP/HTTPS downloads with a clean progress bar ([Rich](https://github.com/Textualize/rich))
* .torrent and magnet link support (single torrent at a time, no seeding)
* Automatic filename selection (from URL or **Content-Disposition** header)
* Resume support for partially downloaded files (HTTP range requests)
* TLS verification (can be disabled with `--no-check-certificate`, insecure!) and proxy support (CLI, config file, or environment variables)
* Automatic retries with exponential backoff
* Optional SHA‑256 checksum verification (auto-fetch `<URL>.sha256`)
* Configuration via TOML (`~/.config/bwget/config.toml`)

## Requirements

* Python 3.8+
* [requests](https://pypi.org/project/requests/)
* [rich](https://pypi.org/project/rich/)
* [libtorrent](https://pypi.org/project/libtorrent/) (for torrent downloads)
* [tomli](https://pypi.org/project/tomli/) (for Python < 3.11) or built‑in `tomllib`

Install via pip:

```bash
pip install requests rich libtorrent tomli
```

## Installation

### From GitHub

Clone the repo and install into your `PATH`:

```bash
git clone https://github.com/Sr-0w/bwget.git
cd bwget
chmod +x bwget.py
sudo mv bwget.py /usr/local/bin/bwget
```

To install the manpage:

```bash
sudo install -Dm644 bwget.1 /usr/share/man/man1/bwget.1
```

### From AUR (Arch Linux)

bwget is packaged in the Arch User Repository. You can install with an AUR helper:

```bash
yay -S bwget
# or
paru -S bwget
```

Or manually:

```bash
git clone https://aur.archlinux.org/bwget.git
cd bwget
makepkg -si
```

This will build and install `/usr/bin/bwget`, the manpage, and completions.

## Usage

```bash
# Download a file
bwget https://example.com/file.tar.gz

# Download a torrent or magnet link
bwget https://example.com/file.torrent
bwget "magnet:?xt=urn:btih:..."

# Force a **fresh** download (disable resume)
bwget -c https://example.com/large.iso

# Download with SHA-256 verification (HTTP or single-file torrent)
bwget --sha256 0123456789abcdef... https://example.com/app.tar.gz

# Use an HTTP proxy
bwget --proxy http://proxy.local:3128 https://example.com/data.zip

# Disable TLS verification (insecure)
bwget --no-check-certificate https://example.com/file.tar.gz
# This makes the connection vulnerable to man-in-the-middle attacks.

# Show version
bwget --version
```

Checksum verification works for regular HTTP downloads and for single-file
torrents when a `--sha256` digest is provided.

## Configuration

On first run, bwget creates a sample config at:

```text
$XDG_CONFIG_HOME/bwget/config.toml
# (defaults to ~/.config/bwget/config.toml)
```

Edit it to tweak defaults:

```toml
[network]
# proxy = "http://user:pass@proxy:8080"
user_agent = "bwget/0.4.0 (Python/3.x)"
max_retries = 3
base_backoff = 1.0
request_timeout = 15
stream_timeout = 30
verify_tls = true

[download]
chunk_size_kb = 256
hash_chunk_size_mb = 1
```

## Contributing

Pull requests and issues welcome!

## Author

Robin Snyders ‹[robin@snyders.xyz](mailto:robin@snyders.xyz)›
