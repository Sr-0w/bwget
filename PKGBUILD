# Maintainer: Your Name <you@example.com>
pkgname=bwget
pkgver=0.3.4
pkgrel=1
pkgdesc="A tiny, single-file Python replacement for wget with progress bar, resume, retries, and sha256 verification"
arch=('any')
url="https://github.com/Sr-0w/bwget"
license=('MIT')
depends=('python' 'python-requests' 'python-rich' 'python-tomli')
source=("bwget.py"
        "bwget.1")
sha256sums=(
  'c55d4f3e7efa0fe37fd4a007375b8a2b963ebac1f0af8f8ad9aaebc4259be500'
  'be46b51cc2c22ac9f248c80e477357b5a99a67009fb12d4c14407889cf3297a7'
)

prepare() {
  sed -i 's/\r$//' "bwget.py" bwget.1
}

package() {
  # script
  install -Dm755 "bwget.py" "$pkgdir/usr/bin/bwget"

  # manpage
  install -Dm644 bwget.1 "$pkgdir/usr/share/man/man1/bwget.1"

}
