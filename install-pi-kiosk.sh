#!/usr/bin/env bash
set -euo pipefail

APP_NAME="homenote"
APP_PORT="8765"
DISPLAY_USER="${SUDO_USER:-${USER}}"
APP_DIR="/home/${DISPLAY_USER}/${APP_NAME}"
KIOSK_URL="http://localhost:${APP_PORT}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this on the Pi with sudo: sudo ./install-pi-kiosk.sh"
  exit 1
fi

echo "[1/8] Installing packages"
apt-get update
apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  xserver-xorg \
  x11-xserver-utils \
  xinit \
  openbox \
  unclutter \
  xdotool

if command -v chromium-browser >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1; then
  echo "Chromium is already installed"
elif apt-cache policy chromium-browser 2>/dev/null | grep -q "Candidate: [^(]"; then
  apt-get install -y chromium-browser
elif apt-cache policy chromium 2>/dev/null | grep -q "Candidate: [^(]"; then
  apt-get install -y chromium
else
  echo "Could not find a Chromium package candidate."
  exit 1
fi

echo "[2/8] Preparing app directory at ${APP_DIR}"
mkdir -p "${APP_DIR}"
cp -R app.py epaper_status.py requirements.txt config.example.json README.md docs static templates "${APP_DIR}/"
if [ ! -f "${APP_DIR}/config.json" ]; then
  cp "${APP_DIR}/config.example.json" "${APP_DIR}/config.json"
fi
chown -R "${DISPLAY_USER}:${DISPLAY_USER}" "${APP_DIR}"

echo "[3/8] Installing Python dependencies"
sudo -u "${DISPLAY_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${DISPLAY_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel
sudo -u "${DISPLAY_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[4/8] Creating HomeNote service"
cat > /etc/systemd/system/homenote.service << EOF
[Unit]
Description=HomeNote TV dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${DISPLAY_USER}
WorkingDirectory=${APP_DIR}
Environment=PORT=${APP_PORT}
Environment=HOMENOTE_CONFIG=${APP_DIR}/config.json
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable homenote.service
systemctl restart homenote.service

echo "[5/8] Disabling screen blanking"
sed -i 's/^#*BLANK_TIME=.*/BLANK_TIME=0/' /etc/kbd/config 2>/dev/null || true
sed -i 's/^#*POWERDOWN_TIME=.*/POWERDOWN_TIME=0/' /etc/kbd/config 2>/dev/null || true
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/10-homenote-blanking.conf << 'EOF'
Section "ServerFlags"
    Option "BlankTime" "0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime" "0"
EndSection
EOF

echo "[6/8] Creating LightDM kiosk session"
CHROMIUM_BIN="$(command -v chromium-browser || command -v chromium)"
cat > /usr/local/bin/homenote-kiosk-session << EOF
#!/usr/bin/env bash
set -e

xset s off
xset -dpms
xset s noblank

unclutter -idle 1 -root &

openbox &

until curl -fsS ${KIOSK_URL}/api/dashboard >/dev/null 2>&1; do
  sleep 1
done

mkdir -p "\$HOME/.config/homenote-chromium"

${CHROMIUM_BIN} \\
  --no-memcheck \\
  --user-data-dir="\$HOME/.config/homenote-chromium" \\
  --password-store=basic \\
  --use-mock-keychain \\
  --disable-gpu \\
  --disable-gpu-compositing \\
  --disable-software-rasterizer=false \\
  --noerrdialogs \\
  --disable-infobars \\
  --disable-features=TranslateUI \\
  --disable-translate \\
  --disable-first-run-ui \\
  --no-first-run \\
  --disable-session-crashed-bubble \\
  --disable-restore-session-state \\
  --check-for-update-interval=31536000 \\
  --start-fullscreen \\
  --kiosk \\
  --app=${KIOSK_URL}
EOF
chmod +x /usr/local/bin/homenote-kiosk-session

cat > /usr/share/xsessions/homenote-kiosk.desktop << EOF
[Desktop Entry]
Name=HomeNote Kiosk
Comment=HomeNote TV dashboard kiosk
Exec=/usr/local/bin/homenote-kiosk-session
Type=Application
EOF

mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-homenote-kiosk.conf << EOF
[Seat:*]
autologin-user=${DISPLAY_USER}
autologin-user-timeout=0
user-session=homenote-kiosk
autologin-session=homenote-kiosk
EOF

if [ -f /etc/lightdm/lightdm.conf ]; then
  if grep -q '^user-session=' /etc/lightdm/lightdm.conf; then
    sed -i 's/^user-session=.*/user-session=homenote-kiosk/' /etc/lightdm/lightdm.conf
  else
    sed -i '/^\[Seat:\*\]/a user-session=homenote-kiosk' /etc/lightdm/lightdm.conf
  fi

  if grep -q '^autologin-session=' /etc/lightdm/lightdm.conf; then
    sed -i 's/^autologin-session=.*/autologin-session=homenote-kiosk/' /etc/lightdm/lightdm.conf
  else
    sed -i '/^\[Seat:\*\]/a autologin-session=homenote-kiosk' /etc/lightdm/lightdm.conf
  fi

  if grep -q '^#*autologin-user-timeout=' /etc/lightdm/lightdm.conf; then
    sed -i 's/^#*autologin-user-timeout=.*/autologin-user-timeout=0/' /etc/lightdm/lightdm.conf
  else
    sed -i '/^\[Seat:\*\]/a autologin-user-timeout=0' /etc/lightdm/lightdm.conf
  fi
fi

echo "[7/8] Removing console kiosk path"
rm -f /etc/systemd/system/getty@tty1.service.d/autologin.conf
rmdir /etc/systemd/system/getty@tty1.service.d 2>/dev/null || true

BASHRC="/home/${DISPLAY_USER}/.bashrc"
if grep -q "HomeNote kiosk startx" "${BASHRC}" 2>/dev/null; then
  sed -i '/# HomeNote kiosk startx/,+3d' "${BASHRC}"
fi
chown "${DISPLAY_USER}:${DISPLAY_USER}" "${BASHRC}"
systemctl set-default graphical.target
systemctl enable lightdm.service

echo "[8/8] Applying Pi display tuning"
BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "${BOOT_CONFIG}" ]; then
  BOOT_CONFIG="/boot/config.txt"
fi
if [ -f "${BOOT_CONFIG}" ]; then
  if grep -q "^gpu_mem=" "${BOOT_CONFIG}"; then
    sed -i 's/^gpu_mem=.*/gpu_mem=128/' "${BOOT_CONFIG}"
  else
    echo "gpu_mem=128" >> "${BOOT_CONFIG}"
  fi
  if ! grep -q "^disable_overscan=" "${BOOT_CONFIG}"; then
    echo "disable_overscan=1" >> "${BOOT_CONFIG}"
  fi
  if grep -q "^#dtparam=spi=on" "${BOOT_CONFIG}"; then
    sed -i 's/^#dtparam=spi=on/dtparam=spi=on/' "${BOOT_CONFIG}"
  elif ! grep -q "^dtparam=spi=on" "${BOOT_CONFIG}"; then
    echo "dtparam=spi=on" >> "${BOOT_CONFIG}"
  fi
fi

cat > /etc/systemd/system/homenote-epaper.service << EOF
[Unit]
Description=HomeNote e-paper status display
After=network-online.target homenote.service
Wants=network-online.target

[Service]
Type=oneshot
User=${DISPLAY_USER}
WorkingDirectory=${APP_DIR}
Environment=GPIOZERO_PIN_FACTORY=lgpio
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/epaper_status.py
EOF

cat > /etc/systemd/system/homenote-epaper.timer << EOF
[Unit]
Description=Refresh HomeNote e-paper status display

[Timer]
OnBootSec=45
OnUnitActiveSec=10min
Unit=homenote-epaper.service

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable homenote-epaper.timer
systemctl restart homenote-epaper.timer

cat > "/home/${DISPLAY_USER}/homenote-status.sh" << EOF
#!/usr/bin/env bash
systemctl --no-pager status homenote.service
echo
echo "Dashboard: ${KIOSK_URL}"
echo "Config: ${APP_DIR}/config.json"
EOF
chmod +x "/home/${DISPLAY_USER}/homenote-status.sh"
chown "${DISPLAY_USER}:${DISPLAY_USER}" "/home/${DISPLAY_USER}/homenote-status.sh"

echo
echo "HomeNote kiosk installed."
echo "Edit ${APP_DIR}/config.json with your private calendar URL and tasks."
echo "Then reboot: sudo reboot"
