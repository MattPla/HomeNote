from __future__ import annotations

import importlib
import os
import socket
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


APP_DIR = Path(__file__).resolve().parent
DRIVER_MODULES = [
    "epd2in13_V4",
    "epd2in13_V3",
    "epd2in13_V2",
    "epd2in13",
]


def add_waveshare_path() -> None:
    site_packages = next((p for p in sys.path if p.endswith("site-packages")), None)
    if not site_packages:
        return
    driver_path = (
        Path(site_packages)
        / "epaper"
        / "e-Paper"
        / "RaspberryPi_JetsonNano"
        / "python"
        / "lib"
    )
    if driver_path.exists():
        sys.path.insert(0, str(driver_path))


def run(command: list[str]) -> str:
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def get_ip() -> str:
    output = run(["hostname", "-I"])
    for part in output.split():
        if "." in part:
            return part
    return "no network"


def service_state(name: str) -> str:
    return run(["systemctl", "is-active", name])


def kiosk_state() -> str:
    output = run(["pgrep", "-af", "chromium.*localhost:8765"])
    return "active" if output else "inactive"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def draw_status(width: int = 250, height: int = 122) -> Image.Image:
    image = Image.new("1", (width, height), 255)
    draw = ImageDraw.Draw(image)
    hostname = socket.gethostname()
    ip = get_ip()
    app = service_state("homenote.service")
    kiosk = kiosk_state()
    stamp = datetime.now().strftime("%b %-d  %-I:%M %p")

    draw.rectangle((0, 0, width - 1, height - 1), outline=0)
    draw.rectangle((0, 0, width - 1, 24), fill=0)
    draw.text((8, 4), "HomeNote", font=font(16, True), fill=255)
    draw.text((width - 74, 6), "STATUS", font=font(12, True), fill=255)

    y = 31
    lines = [
        ("Host", hostname),
        ("IP", ip),
        ("App", app),
        ("Kiosk", kiosk),
        ("URL", f"http://{ip}:8765"),
    ]
    label_font = font(12, True)
    value_font = font(13)
    for label, value in lines:
        draw.text((8, y), f"{label}:", font=label_font, fill=0)
        draw.text((58, y), value, font=value_font, fill=0)
        y += 17

    draw.text((8, height - 15), stamp, font=font(10), fill=0)
    return image


def load_display():
    add_waveshare_path()
    errors = []
    for module_name in DRIVER_MODULES:
        try:
            module = importlib.import_module(f"waveshare_epd.{module_name}")
            return module.EPD(), module_name
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")
    raise RuntimeError("; ".join(errors))


def main() -> int:
    epd, module_name = load_display()
    epd.init()

    width = max(epd.width, epd.height)
    height = min(epd.width, epd.height)
    image = draw_status(width, height)
    epd.display(epd.getbuffer(image))

    if hasattr(epd, "sleep"):
        epd.sleep()
    print(f"Updated e-paper status using {module_name}: {width}x{height}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
