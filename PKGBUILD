# Maintainer: Robin Snyders <robin@snyders.xyz>
pkgname=bwget
pkgver=0.4.0
pkgrel=1
pkgdesc="A tiny, single-file Python replacement for wget with progress bar, resume, retries, and sha256 verification"
arch=('any')
url="https://github.com/Sr-0w/bwget"
license=('MIT')
depends=('python' 'python-requests' 'python-rich' 'python-libtorrent' 'python-tomli')
source=("bwget.py"
        "bwget.1")
sha256sums=(
  '2a7c2904cf096999601068b6cf40b4daffde76c25e7f592184945433863015f0'
  '5589b53c6d3ed396a37ee7b19f49b78387e01606698fa3fd35d726fb304cd7ce'
)

prepare() {
  sed -i 's/\r$//' "bwget.py" bwget.1
}

package() {
  # Install script
  install -Dm755 "bwget.py" "$pkgdir/usr/bin/bwget"

  # Install man page
  install -Dm644 bwget.1 "$pkgdir/usr/share/man/man1/bwget.1"

}
