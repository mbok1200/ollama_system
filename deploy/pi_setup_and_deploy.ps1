<#
PowerShell wrapper for deploy/pi_setup_and_deploy.sh
Usage (remote deploy from Windows):
  .\deploy\pi_setup_and_deploy.ps1 --host pi.example.local --ssh-user pi --ssh-key C:\path\to\key

Notes:
- This script uses `tar` + `ssh` to stream files to the Pi and then runs the same
  sequence of commands the original bash script performs.
- For local mode (--local) run the original bash script on the Pi (WSL on Windows
  without distributions will not work). This wrapper will error if --local is used
  on native Windows.
#>

param(
    [switch]$Local,
    [string]$HostName = "",
    [string]$SshUser = "pi",
    [string]$SshKey = "",
    [string]$Domain = "",
    [string]$Email = ""
)

function Show-Usage {
    Write-Host "Usage: .\deploy\pi_setup_and_deploy.ps1 [--local] [--host PI_HOST] [--ssh-user SSH_USER] [--ssh-key SSH_KEY] [--domain DOMAIN --email EMAIL]"
    exit 1
}

if (-not $Local -and [string]::IsNullOrWhiteSpace($HostName)) {
    Write-Host "--host is required when not running --local" -ForegroundColor Red
    Show-Usage
}
if (-not [string]::IsNullOrWhiteSpace($Domain) -and [string]::IsNullOrWhiteSpace($Email)) {
    Write-Host "--email is required when --domain is provided" -ForegroundColor Red
    Show-Usage
}

if ($Local) {
    # Running locally on Windows is not supported for apt/systemd/nginx steps.
    if ($IsWindows) {
        Write-Host "--local mode must be run on the Raspberry Pi (Linux)." -ForegroundColor Yellow
        Write-Host "Options: run the original script on the Pi, install WSL+distribution, or use remote mode from Windows." -ForegroundColor Yellow
        exit 1
    }
}

# Build ssh options
$sshOptions = "-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"
if (-not [string]::IsNullOrWhiteSpace($SshKey)) {
    $sshOptions = "-i `"$SshKey`" $sshOptions"
}

$remote = "$SshUser@$HostName"

Write-Host "==> Ensuring user 'bradi' exists on $HostName"
$userScript = @'
set -e
if ! id -u bradi >/dev/null 2>&1; then
  sudo adduser --disabled-password --gecos "" bradi
  sudo usermod -aG sudo bradi
  echo "Created user bradi"
else
  echo "User bradi already exists"
fi
'@

Write-Host "==> Streaming project to remote and extracting to /home/bradi/ollama_system"

# Exclude list for tar
$excludes = @('.venv', '.git', '__pycache__')
$excludeArgs = $excludes | ForEach-Object { "--exclude='$_'" } -join ' '

if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    Write-Host "`nError: 'tar' command not found on this machine. Install Windows tar or use WSL." -ForegroundColor Red
    exit 1
}

# Create remote dir and stream files
$sshRemoteCmd = "sudo mkdir -p /home/bradi/ollama_system && sudo tar -xzf - -C /home/bradi/ollama_system"

Write-Host "Packing and sending files (this may take a while)..."

$cmd = "tar -czf - $excludeArgs . | ssh $sshOptions $remote '$sshRemoteCmd'"

Write-Host "Running: $cmd"
# Execute the pipeline using native shell
$ps = [System.Diagnostics.Process]::Start('powershell', "-NoProfile -Command $cmd")
$ps.WaitForExit()
if ($ps.ExitCode -ne 0) {
    Write-Host "Error: file transfer failed (exit code $($ps.ExitCode))." -ForegroundColor Red
    exit 1
}

Write-Host "==> Fixing permissions on remote"
$chownCmd = "sudo chown -R bradi:bradi /home/bradi/ollama_system"
ssh $sshOptions $remote $chownCmd

Write-Host "==> Installing system packages and Python deps on remote"
$installScript = @'
set -e
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
cd /home/bradi/ollama_system
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
'@

$installScript | ssh $sshOptions $remote 'bash -s'

Write-Host "==> Installing systemd unit and nginx config"
if (-not [string]::IsNullOrWhiteSpace($Domain)) {
    $sedDomain = "sed 's/__DOMAIN__/${Domain//\//\\\/}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system.conf > /tmp/ollama_system.conf"
    $remoteCommands = @(
        $sedDomain,
        'sudo cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service',
        'sudo cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf',
        'sudo ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable --now ollama_system',
        'sudo nginx -t',
        'sudo systemctl restart nginx'
    ) -join '; '
    ssh $sshOptions $remote $remoteCommands
    Write-Host "==> Obtaining TLS certificate for $Domain (may prompt)"
    ssh $sshOptions $remote "sudo certbot --nginx -d $Domain --non-interactive --agree-tos -m $Email || echo 'Certbot failed or already present'"
} else {
    $sedHost = "sed 's/__HOST__/${HostName//\//\\\/}/g' /home/bradi/ollama_system/deploy/nginx/ollama_system_nossl.conf > /tmp/ollama_system.conf"
    $remoteCommands = @(
        $sedHost,
        'sudo cp /home/bradi/ollama_system/deploy/systemd/ollama_system.service /etc/systemd/system/ollama_system.service',
        'sudo cp /tmp/ollama_system.conf /etc/nginx/sites-available/ollama_system.conf',
        'sudo ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable --now ollama_system',
        'sudo nginx -t',
        'sudo systemctl restart nginx'
    ) -join '; '
    ssh $sshOptions $remote $remoteCommands
    Write-Host "==> No domain provided; serving over HTTP"
}

Write-Host "==> Deployment finished. Tail logs with: ssh $SshUser@$HostName 'sudo journalctl -u ollama_system -f'"
