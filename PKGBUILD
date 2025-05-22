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
  '6e7963330622b96dafe48768507e7a0d1c3f7188b08bf1b6c8aa6447bba8a4b6'
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
