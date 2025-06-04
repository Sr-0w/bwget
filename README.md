# 🚀 bwget - Better Wget

**bwget** is a minimalist yet powerful single-file downloader crafted in Python, designed to simplify and enhance your downloading experience. Inspired by the legendary GNU `wget`, bwget adds intuitive features, seamless torrent support, and sleek progress visuals—all within a compact script.

---

## 🌟 Key Features

* 🌐 **HTTP/HTTPS Downloads:** Effortlessly download files with an elegant progress bar powered by Rich.
* 🔗 **Torrent Support:** Download `.torrent` files and magnet links with ease (single torrent at a time, no seeding).
* 📁 **Automatic Filename Detection:** Picks the perfect filename from URLs or server headers.
* ⏳ **Resume Capability:** Seamlessly continue interrupted downloads.
* 🔐 **Secure Connections:** Robust TLS verification, with an option to bypass (`--no-check-certificate`).
* 🛡️ **SHA-256 Verification:** Automatically verifies file integrity via SHA-256.
* 🔄 **Automatic Retries:** Smart retries with exponential backoff for robust downloads.
* 📃 **Batch Downloads:** Handle multiple downloads effortlessly from a list file (`urls.txt`).
* 🛠️ **Configurable:** Customize behavior easily through a convenient TOML config file.

---

## 🛠️ Requirements

* **Python 3.8+**
* `requests`, `rich`, and `libtorrent` packages
* `tomli` (Python <3.11) or built-in `tomllib` (Python ≥3.11)

Install all dependencies quickly:

```bash
pip install requests rich libtorrent tomli
```

---

## ⚙️ Installation

### 📂 From Source

Clone and install quickly:

```bash
git clone https://github.com/Sr-0w/bwget.git
cd bwget
chmod +x bwget.py
sudo mv bwget.py /usr/local/bin/bwget
```

Optionally, install the provided man page:

```bash
sudo install -Dm644 bwget.1 /usr/share/man/man1/bwget.1
```

### 📦 Packages

* **Arch Linux (AUR)**: [bwget](https://aur.archlinux.org/packages/bwget)
* **Fedora (COPR)**: [bwget](https://copr.fedorainfracloud.org/coprs/srobin/bwget/)

Install from AUR manually:

```bash
git clone https://aur.archlinux.org/bwget.git
cd bwget
makepkg -si
```

---

## 📌 Usage Examples

Simple file download:

```bash
bwget https://example.com/file.tar.gz
```

Download torrent or magnet link:

```bash
bwget https://example.com/file.torrent
bwget "magnet:?xt=urn:btih:..."
```

Force new download (ignore resume):

```bash
bwget -c https://example.com/large.iso
```

SHA-256 verification:

```bash
bwget --sha256 0123456789abcdef... https://example.com/app.tar.gz
```

Using an HTTP proxy:

```bash
bwget --proxy http://proxy.local:3128 https://example.com/data.zip
```

Disable TLS verification:

```bash
bwget --no-check-certificate https://example.com/file.tar.gz
```

Batch download:

```bash
bwget -i urls.txt
```

Custom user-agent:

```bash
bwget -U "MyDownloader/1.0" https://example.com/file.zip
```

Check version:

```bash
bwget --version
```

---

## 🔧 Configuration

On first launch, bwget creates a default configuration at:

```
~/.config/bwget/config.toml
```

Customize settings like proxies, retries, timeouts, and chunk sizes directly:

```toml
[network]
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

---

## 🤝 Contributing

Your contributions are welcome! Feel free to open issues, request features, or submit pull requests to help improve bwget.

---

## 🙋 Author

Crafted with care by **Robin Snyders** ([robin@snyders.xyz](mailto:robin@snyders.xyz))

---

Enjoy using **bwget**—making downloading simpler, faster, and better!
