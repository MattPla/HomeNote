from __future__ import annotations

import os
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = Path(os.environ.get("HOMENOTE_LOCAL_CONFIG", ROOT / "config.json"))
TARGET = os.environ.get("HOMENOTE_PI_TARGET", "homenote.local")
USER = os.environ.get("HOMENOTE_PI_USER", "pi")
PASSWORD = os.environ["HOMENOTE_PI_PASSWORD"]
REMOTE_CONFIG = os.environ.get("HOMENOTE_PI_CONFIG", f"/home/{USER}/homenote/config.json")


def main() -> int:
    if not LOCAL_CONFIG.exists():
        print(f"Local config not found: {LOCAL_CONFIG}")
        print("Copy config.example.json to config.json and edit it first.")
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(TARGET, username=USER, password=PASSWORD, look_for_keys=False, allow_agent=False, timeout=15)
    try:
        sftp = client.open_sftp()
        try:
            print(f"Uploading {LOCAL_CONFIG} to {USER}@{TARGET}:{REMOTE_CONFIG}")
            sftp.put(str(LOCAL_CONFIG), REMOTE_CONFIG)
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

