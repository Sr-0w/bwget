# bwget

**Better Wget** in Python — a tiny single-file downloader with the essentials of GNU `wget`.

![bwget demo](https://pouch.jumpshare.com/preview/P97VWVAAv80eYgIit58iPW7Z9p5B2Gii1s3TPaJwO_8I-1Ix-3go_5QyWkuWnjxU2A4Rb8yKhJS2MLfj-2Drjw5QoTvJ8_fU7PXfI7G3wVM)

---

## Features

- HTTP/HTTPS downloads with a Rich progress bar
- `.torrent` and magnet link support (one torrent at a time, no seeding)
- Automatic filename detection from the URL or `Content-Disposition`
- Resume partially downloaded files
- TLS verification (can be disabled with `--no-check-certificate`) and proxy support
- Automatic retries with exponential backoff
- Optional SHA‑256 verification (`<URL>.sha256` auto-fetch)
- Batch downloads from a list (`-i urls.txt` or `urls.txt`)
- TOML configuration file at `~/.config/bwget/config.toml`

## Requirements

- Python 3.8 or newer
- [requests](https://pypi.org/project/requests/)
- [rich](https://pypi.org/project/rich/)
- [libtorrent](https://pypi.org/project/libtorrent/) for torrent downloads
- `tomli` on Python < 3.11, otherwise the built‑in `tomllib`

Install dependencies with pip:

```bash
pip install requests rich libtorrent tomli
```

## Installation

### From source

```bash
git clone https://github.com/Sr-0w/bwget.git
cd bwget
chmod +x bwget.py
sudo mv bwget.py /usr/local/bin/bwget
```

Install the man page if you want:

```bash
sudo install -Dm644 bwget.1 /usr/share/man/man1/bwget.1
```

### Packages

- **AUR**: <https://aur.archlinux.org/packages/bwget>
- **COPR**: <https://copr.fedorainfracloud.org/coprs/srobin/bwget/>

Arch users can also build the package manually:

```bash
git clone https://aur.archlinux.org/bwget.git
cd bwget
makepkg -si
```

## Usage

```bash
# Download a file
bwget https://example.com/file.tar.gz

# Download a torrent or magnet link
bwget https://example.com/file.torrent
bwget "magnet:?xt=urn:btih:..."

# Force a fresh download (ignore resume data)
bwget -c https://example.com/large.iso

# SHA‑256 verification (HTTP or single-file torrent)
bwget --sha256 0123456789abcdef... https://example.com/app.tar.gz

# Use an HTTP proxy
bwget --proxy http://proxy.local:3128 https://example.com/data.zip

# Disable TLS verification (insecure)
bwget --no-check-certificate https://example.com/file.tar.gz

# Download many URLs from a file
bwget -i urls.txt

# Custom User-Agent
bwget -U "MyDownloader/1.0" https://example.com/file.zip

# Show version
bwget --version
```

Checksum verification works for regular HTTP downloads and for single-file torrents when a `--sha256` digest is provided.

## Configuration

On first run bwget creates a sample config at:

```text
$XDG_CONFIG_HOME/bwget/config.toml
# (defaults to ~/.config/bwget/config.toml)
```

Example options:

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

Feel free to open issues or pull requests.

## Author

Robin Snyders <robin@snyders.xyz>
