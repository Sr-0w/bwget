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
  'bee8bac671b028cc3b293f4e870fd4dbf536a18bc137fcddd37b5c806f5f03e9'
  '42385ac8e16d52fb05c727e6445db8bd1b7f65f4de03936febe812ec11bac2e8'
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
