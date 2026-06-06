# Raspberry Pi Install

HomeNote is intended for Raspberry Pi OS with a desktop stack available through LightDM, Openbox, and Chromium.

Tested target:

- Raspberry Pi Zero 2 W
- Raspberry Pi OS
- HDMI TV
- Optional Waveshare 2.13-inch e-paper HAT V4

## Prepare The Pi

Enable SSH on the Pi and make sure it is on your network.

Update packages:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

Clone or copy this project to the Pi.

## Install

From the project folder on the Pi:

```bash
sudo ./install-pi-kiosk.sh
```

The installer:

- Installs Python, Chromium, Openbox, LightDM kiosk pieces, and support packages.
- Copies the app to `~/homenote`.
- Creates a Python virtual environment.
- Creates `homenote.service`.
- Creates a LightDM autologin kiosk session.
- Disables screen blanking.
- Enables optional e-paper status timer.

## Configure

Edit:

```bash
nano ~/homenote/config.json
```

Restart:

```bash
sudo systemctl restart homenote.service
sudo systemctl restart lightdm.service
```

## Useful Commands

Dashboard status:

```bash
systemctl status homenote.service
```

Kiosk status:

```bash
systemctl status lightdm.service
```

Logs:

```bash
journalctl -u homenote.service -n 100 --no-pager
```

Restart app:

```bash
sudo systemctl restart homenote.service
```

Restart kiosk display:

```bash
sudo systemctl restart lightdm.service
```

Reboot:

```bash
sudo reboot
```

## Access From Another Computer

Find the Pi IP address:

```bash
hostname -I
```

Then open:

```text
http://PI_IP_ADDRESS:8765
```

