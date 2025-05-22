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
  '9e8b431ff5f1f2bf8f792b73b44343db2d293b341b2a5ff38e861f990e1d7687'
  '70ecb04cfb2965d2392adcdfc5abdbbfe1296fcb055867b77df41200c67035ff'
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
