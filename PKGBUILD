# Maintainer: Your Name <you@example.com>
pkgname=bwget
pkgver=0.3.6
pkgrel=1
pkgdesc="A tiny, single-file Python replacement for wget with progress bar, resume, retries, and sha256 verification"
arch=('any')
url="https://github.com/Sr-0w/bwget"
license=('MIT')
depends=('python' 'python-requests' 'python-rich' 'python-tomli')
source=("bwget.py"
        "bwget.1")
sha256sums=(
  '26c193ce9acee8e2f5104d9cd65c1f59ace772a4b006dc5ae80d4c250148762b'
  '78370b058f94a75249707d959d170e1aa55d8ef6b0e0129fa0db9ef746c60743'
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
