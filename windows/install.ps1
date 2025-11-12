param(
    [string]$PythonPath = "python",
    [switch]$RegisterTask,
    [string]$TaskName = "SecureUSB",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$requirements = Join-Path $repoRoot "windows\requirements.txt"
$appScript = Join-Path $repoRoot "windows\src\app.py"
$configDir = Join-Path ${env:PROGRAMDATA} "SecureUSB"
$pointerFile = Join-Path $configDir "config_dir.txt"

Write-Host "== SecureUSB Windows installer =="
Write-Host "Repo: $repoRoot"
Write-Host "Python: $PythonPath"

Write-Host "`nInstalling Python dependencies..."
& $PythonPath -m pip install -r $requirements

if (-not (Test-Path $configDir)) {
    Write-Host "Creating shared configuration directory: $configDir"
    New-Item -ItemType Directory -Force -Path $configDir | Out-Null
}

Set-Content -Path $pointerFile -Value $configDir
Write-Host "Config pointer written to $pointerFile"

if ($RegisterTask) {
    Write-Host "Registering Scheduled Task '$TaskName'..."
    $action = New-ScheduledTaskAction -Execute $PythonPath -Argument $appScript
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    try {
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -RunLevel Highest -Force:$Force
    } catch {
        Write-Warning "Failed to register scheduled task: $_"
    }
}

Write-Host "`nNext steps:"
Write-Host "1. Run 'python windows/src/setup_cli.py' to generate the TOTP secret."
Write-Host "2. Run 'python windows/src/app.py' (as Administrator)."
