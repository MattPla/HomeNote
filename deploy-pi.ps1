param(
  [string]$Target = "pi@homenote.local",
  [string]$RemoteDir = "/tmp/homenote-source"
)

$ErrorActionPreference = "Stop"

$files = @(
  "app.py",
  "epaper_status.py",
  "requirements.txt",
  "config.example.json",
  "install-pi-kiosk.sh",
  "README.md",
  "docs",
  "static",
  "templates"
)

ssh $Target "mkdir -p '$RemoteDir'"
scp -r $files "$Target`:$RemoteDir/"
ssh -t $Target "cd '$RemoteDir' && sudo bash install-pi-kiosk.sh"
