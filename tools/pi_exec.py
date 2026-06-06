from __future__ import annotations

import os
import sys

import paramiko


target = os.environ.get("HOMENOTE_PI_TARGET", "homenote.local")
user = os.environ.get("HOMENOTE_PI_USER", "pi")
password = os.environ["HOMENOTE_PI_PASSWORD"]
command = " ".join(sys.argv[1:])

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(target, username=user, password=password, look_for_keys=False, allow_agent=False, timeout=15)
try:
    stdin, stdout, stderr = client.exec_command(command)
    sys.stdout.buffer.write(stdout.read())
    sys.stderr.buffer.write(stderr.read())
    raise SystemExit(stdout.channel.recv_exit_status())
finally:
    client.close()
