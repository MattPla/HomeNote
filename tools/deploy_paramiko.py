from __future__ import annotations

import os
import posixpath
import shlex
import socket
import stat
import sys
import time
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
TARGET = os.environ.get("HOMENOTE_PI_TARGET", "homenote.local")
USER = os.environ.get("HOMENOTE_PI_USER", "pi")
PASSWORD = os.environ["HOMENOTE_PI_PASSWORD"]
REMOTE_DIR = os.environ.get("HOMENOTE_PI_REMOTE_DIR", f"/home/{USER}/homenote-source")

UPLOADS = [
    "app.py",
    "epaper_status.py",
    "requirements.txt",
    "config.example.json",
    "install-pi-kiosk.sh",
    "README.md",
    "docs",
    "static",
    "templates",
]


def connect() -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        TARGET,
        username=USER,
        password=PASSWORD,
        timeout=15,
        banner_timeout=15,
        auth_timeout=15,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def run(client: paramiko.SSHClient, command: str, sudo: bool = False) -> int:
    if sudo:
        command = f"sudo -S -p '' {command}"
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport is not available")
    channel = transport.open_session()
    channel.set_combine_stderr(True)
    channel.exec_command(command)
    if sudo:
        channel.send(PASSWORD + "\n")

    while True:
        if channel.recv_ready():
            sys.stdout.buffer.write(channel.recv(4096))
            sys.stdout.buffer.flush()
        if channel.exit_status_ready():
            while channel.recv_ready():
                sys.stdout.buffer.write(channel.recv(4096))
                sys.stdout.buffer.flush()
            return channel.recv_exit_status()
        time.sleep(0.1)


def ensure_remote_dir(sftp: paramiko.SFTPClient, path: str) -> None:
    parts = [part for part in path.split("/") if part]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload_path(sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    if local.is_dir():
        ensure_remote_dir(sftp, remote)
        for child in local.iterdir():
            upload_path(sftp, child, posixpath.join(remote, child.name))
        return

    ensure_remote_dir(sftp, posixpath.dirname(remote))
    sftp.put(str(local), remote)
    mode = local.stat().st_mode
    if mode & stat.S_IXUSR:
        sftp.chmod(remote, 0o755)


def main() -> int:
    print(f"Connecting to {USER}@{TARGET}...")
    with connect() as client:
        sftp = client.open_sftp()
        try:
            print(f"Uploading HomeNote to {REMOTE_DIR}...")
            run(client, f"mkdir -p {REMOTE_DIR!r}")
            for item in UPLOADS:
                upload_path(sftp, ROOT / item, posixpath.join(REMOTE_DIR, item))
        finally:
            sftp.close()

        print("Running Pi installer...")
        code = run(client, f"bash -lc {shlex.quote(f'cd {shlex.quote(REMOTE_DIR)} && bash install-pi-kiosk.sh')}", sudo=True)
        if code != 0:
            print(f"Installer exited with status {code}")
            return code
        print("Install finished.")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (socket.timeout, paramiko.SSHException, OSError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
