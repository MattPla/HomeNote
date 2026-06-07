from __future__ import annotations

import os
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
TARGET = os.environ.get("HOMENOTE_PI_TARGET", "homenote.local")
USER = os.environ.get("HOMENOTE_PI_USER", "pi")
PASSWORD = os.environ["HOMENOTE_PI_PASSWORD"]
REMOTE_DIR = os.environ.get("HOMENOTE_PI_APP_DIR", f"/home/{USER}/homenote")
FILES = ("google-credentials.json", "google-token.json")


def main() -> int:
    missing = [name for name in FILES if not (ROOT / name).exists()]
    if missing:
        print(f"Missing local OAuth file(s): {', '.join(missing)}")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(TARGET, username=USER, password=PASSWORD, look_for_keys=False, allow_agent=False, timeout=15)
    try:
        sftp = client.open_sftp()
        try:
            for name in FILES:
                remote_path = f"{REMOTE_DIR}/{name}"
                print(f"Uploading {name} to {remote_path}")
                sftp.put(str(ROOT / name), remote_path)
        finally:
            sftp.close()

        stdin, stdout, stderr = client.exec_command("sudo -S -p '' systemctl restart homenote.service")
        stdin.write(PASSWORD + "\n")
        stdin.flush()
        print(stdout.read().decode("utf-8", errors="replace"), end="")
        print(stderr.read().decode("utf-8", errors="replace"), end="")
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())

