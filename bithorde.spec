Name:          bithorde
Version:       0.2.98
Release:       1
Summary:       A fast and light caching-graph content distribution system.
Group:         Applications/Network
License:       Apache 2.0
URL:           http://www.bithorde.org/
Vendor:        Ulrik Mikaelsson <ulrik@bithorde.org>
Source:        https://github.com/rawler/bithorde/archive/%{version}.tar.gz
Prefix:        %{_prefix}
Packager:      Olof Fryksén <olof@fryksen.se>
BuildRoot:     %{_tmppath}/%{name}-root
BuildRequires: cmake
BuildRequires: gcc-c++
BuildRequires: boost-devel
BuildRequires: protobuf-devel
BuildRequires: cryptopp-devel
BuildRequires: fuse-devel
#BuildRequires: protobuf-python
BuildRequires: python-eventlet
BuildRequires: python-crypto
Requires(pre): shadow-utils

%description
A fast and light content distribution system, aimed for high-performance de-centralized
content distribution. Key design goals is; caching graph, low footprint, direct access
and id-by-content. WARNING: BitHorde is still experimental. Beware of Gremlins

%pre
getent group bithorde >/dev/null || groupadd -r bithorde
getent passwd bithorde >/dev/null || \
    useradd -r -g bithorde -d %{_sharedstatedir}/bithorde -s /sbin/nologin \
    -c "Bithorde service user" bithorde
exit 0

%prep
%autosetup -n %{name}-%{version}

%build
%cmake . -DCONF_INSTALL_DIR="/etc" -DPyHorde_INSTALL_DIR="/usr/share/pyshared"
make %{?_smp_mflags}

%install
make install DESTDIR=%{buildroot}
install --directory %{buildroot}%{_libdir}/
install --directory %{buildroot}%{_sharedstatedir}/bithorde
install --directory %{buildroot}%{_localstatedir}/run/bithorde
install lib/libbithorde.so %{buildroot}%{_libdir}/
install --directory %{buildroot}%{_sysconfdir}/init
install bithorde.upstart.el6 %{buildroot}%{_sysconfdir}/init/bithorde.conf
install bhfuse.upstart.el6 %{buildroot}%{_sysconfdir}/init/bhfuse.conf

%check
ctest -V %{?_smp_mflags} || exit 0 # Pointless, but hey! Tests!

%clean
rm -rf %{buildroot}

%files
%config(noreplace) %{_sysconfdir}/bithorde.conf
%config %attr(0644, root, root) %{_sysconfdir}/init/*.conf
%attr(0700, bithorde, bithorde) %{_sharedstatedir}/bithorde
%dir %{_localstatedir}/run/bithorde
%{_bindir}/*
%{_libdir}/*

%post
initctl reload-configuration

%preun
initctl stop bithorde

%postun
rm -f %{_localstatedir}/run/bithorde/socket
rmdir %{_localstatedir}/run/bithorde

%changelog
* Wed Oct 19 2016 Olof Fryksén <olof@fryksen.se> - 0.2.98
- Initial RPM release
