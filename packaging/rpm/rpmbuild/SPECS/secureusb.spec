Name:           secureusb
Version:        0.1
Release:        1%{?dist}
Summary:        Secure USB device authorization service
License:        MIT
URL:            https://github.com/yourusername/secureusb
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
Requires:       python3, python3-gi, python3-dbus, systemd, udev, polkit-1

%description
SecureUSB blocks USB ports by default and prompts for TOTP-based authorization
whenever a new device is connected. It includes a GTK4 client, a root daemon,
udev/systemd integration, and logging support for auditing.

%prep
%setup -q

%build
# No build step required (pure Python)

%install
rm -rf %{buildroot}
install -d %{buildroot}/opt/secureusb
cp -a . %{buildroot}/opt/secureusb

install -d %{buildroot}/etc/systemd/system
install -m 0644 data/systemd/secureusb.service %{buildroot}/etc/systemd/system/secureusb.service

install -d %{buildroot}/etc/udev/rules.d
install -m 0644 data/udev/99-secureusb.rules %{buildroot}/etc/udev/rules.d/99-secureusb.rules

install -d %{buildroot}/usr/share/polkit-1/actions
install -m 0644 data/polkit/org.secureusb.policy %{buildroot}/usr/share/polkit-1/actions/org.secureusb.policy

install -d %{buildroot}/etc/dbus-1/system.d
install -m 0644 data/dbus/org.secureusb.Daemon.conf %{buildroot}/etc/dbus-1/system.d/org.secureusb.Daemon.conf

install -d %{buildroot}/usr/share/icons/hicolor/scalable/apps
install -m 0644 data/icons/hicolor/scalable/apps/*.svg %{buildroot}/usr/share/icons/hicolor/scalable/apps/

install -d %{buildroot}/etc/xdg/autostart
install -m 0644 data/desktop/secureusb-client.desktop %{buildroot}/etc/xdg/autostart/secureusb-client.desktop
install -m 0644 data/desktop/secureusb-indicator.desktop %{buildroot}/etc/xdg/autostart/secureusb-indicator.desktop

install -d %{buildroot}/usr/local/bin
cat > %{buildroot}/usr/local/bin/secureusb-daemon <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/daemon/service.py "$@"
EOF
chmod 0755 %{buildroot}/usr/local/bin/secureusb-daemon

cat > %{buildroot}/usr/local/bin/secureusb-setup <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/setup_wizard.py "$@"
EOF
chmod 0755 %{buildroot}/usr/local/bin/secureusb-setup

cat > %{buildroot}/usr/local/bin/secureusb-client <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/client.py "$@"
EOF
chmod 0755 %{buildroot}/usr/local/bin/secureusb-client

cat > %{buildroot}/usr/local/bin/secureusb-indicator <<'EOF'
#!/bin/bash
cd /opt/secureusb
exec python3 src/gui/indicator.py "$@"
EOF
chmod 0755 %{buildroot}/usr/local/bin/secureusb-indicator

%post
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -eq 1 ]; then
    /bin/systemctl enable --now secureusb.service >/dev/null 2>&1 || :
fi
# Update icon cache
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || :
fi

%preun
if [ $1 -eq 0 ]; then
    /bin/systemctl disable --now secureusb.service >/dev/null 2>&1 || :
fi
/bin/systemctl daemon-reload >/dev/null 2>&1 || :

%files
%license LICENSE
%doc README.md QUICKSTART.md docs
/opt/secureusb
/etc/systemd/system/secureusb.service
/etc/udev/rules.d/99-secureusb.rules
/usr/share/polkit-1/actions/org.secureusb.policy
/etc/dbus-1/system.d/org.secureusb.Daemon.conf
/usr/share/icons/hicolor/scalable/apps/*.svg
/etc/xdg/autostart/secureusb-client.desktop
/etc/xdg/autostart/secureusb-indicator.desktop
/usr/local/bin/secureusb-daemon
/usr/local/bin/secureusb-setup
/usr/local/bin/secureusb-client
/usr/local/bin/secureusb-indicator

%changelog
* Sat Feb 15 2025 SecureUSB Automation <maintainers@secureusb.local> - 0.1-1
- Initial RPM packaging
