Name:           bwget
Version:        0.4.0
Release:        1%{?dist}
Summary:        Tiny single-file Python replacement for wget

License:        MIT
URL:            https://github.com/Sr-0w/bwget
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz#/bwget-%{version}.tar.gz

BuildArch:      noarch

# Build-time dependencies
BuildRequires:  python3-devel
BuildRequires:  python3dist(requests) python3dist(rich)
BuildRequires:  python3dist(libtorrent)
BuildRequires:  (python3dist(tomli) if %{python3_pkgversion} < 3.11)

# Runtime dependencies – same list
Requires:       python3dist(requests) python3dist(rich)
Requires:       python3dist(libtorrent)
Requires:       (python3dist(tomli) if %{python3_pkgversion} < 3.11)

%description
Better Wget in Python: single-file download tool with progress bar, resume,
retries and SHA-256 verification.

%prep
%autosetup -n %{name}-%{version}

%build
# Fix the shebang to /usr/bin/python3
%py3_shebang_fix bwget.py

%install
# Install script
install -Dm0755 bwget.py %{buildroot}%{_bindir}/bwget
# Install man page
install -Dm0644 bwget.1 %{buildroot}%{_mandir}/man1/bwget.1

%files
%license LICENSE
%doc README.md
%{_bindir}/bwget
%{_mandir}/man1/bwget.1*

%changelog
* Tue Jun 03 2025 Sr-0w <robin@snyders.xyz> - 0.4.0-1
- First RPM/COPR release
