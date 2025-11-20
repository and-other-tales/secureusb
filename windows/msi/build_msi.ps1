#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build a Windows MSI installer for SecureUSB.

.DESCRIPTION
    This script uses WiX Toolset to create a Windows x64 MSI installer package.
    It compiles the WiX source files, harvests application files, and generates
    the final MSI installer.

.PARAMETER Version
    The version number for the installer (default: 1.0.0)

.PARAMETER WixPath
    Path to WiX Toolset bin directory (default: auto-detect from PATH or common locations)

.EXAMPLE
    .\build_msi.ps1 -Version 1.0.0
    .\build_msi.ps1 -Version 1.2.3 -WixPath "C:\Program Files (x86)\WiX Toolset v3.11\bin"
#>

param(
    [Parameter(Position=0)]
    [string]$Version = "1.0.0",

    [Parameter()]
    [string]$WixPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Colors for output
function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Locate WiX Toolset
function Find-WixToolset {
    param([string]$CustomPath)

    if ($CustomPath -and (Test-Path "$CustomPath\candle.exe")) {
        return $CustomPath
    }

    # Check PATH
    $candleCmd = Get-Command candle.exe -ErrorAction SilentlyContinue
    if ($candleCmd) {
        return Split-Path $candleCmd.Source
    }

    # Check common installation locations
    $commonPaths = @(
        "${env:ProgramFiles(x86)}\WiX Toolset v3.11\bin",
        "${env:ProgramFiles(x86)}\WiX Toolset v3.14\bin",
        "${env:ProgramFiles}\WiX Toolset v3.11\bin",
        "${env:ProgramFiles}\WiX Toolset v3.14\bin",
        "${env:ProgramFiles(x86)}\WiX Toolset v4.0\bin",
        "${env:ProgramFiles}\WiX Toolset v4.0\bin"
    )

    foreach ($path in $commonPaths) {
        if (Test-Path "$path\candle.exe") {
            return $path
        }
    }

    return $null
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Yellow
Write-Host " SecureUSB Windows MSI Builder (x64)" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Yellow
Write-Host "Version: $Version"
Write-Host ""

# Script and repository paths
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BuildDir = Join-Path $ScriptDir "build"
$ObjDir = Join-Path $BuildDir "obj"
$OutputDir = Join-Path $ScriptDir "dist"

# Locate WiX
Write-Step "Locating WiX Toolset..."
$WixBinPath = Find-WixToolset -CustomPath $WixPath

if (-not $WixBinPath) {
    Write-Error-Custom "WiX Toolset not found!"
    Write-Host ""
    Write-Host "Please install WiX Toolset v3.11+ from:"
    Write-Host "  https://wixtoolset.org/releases/"
    Write-Host ""
    Write-Host "Or specify the path manually:"
    Write-Host "  .\build_msi.ps1 -WixPath 'C:\Path\To\WiX\bin'"
    exit 1
}

Write-Success "Found WiX at: $WixBinPath"
$Candle = Join-Path $WixBinPath "candle.exe"
$Light = Join-Path $WixBinPath "light.exe"
$Heat = Join-Path $WixBinPath "heat.exe"

# Clean and create build directories
Write-Step "Preparing build directories..."
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}
New-Item -ItemType Directory -Force -Path $ObjDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
Write-Success "Build directories ready"

# Harvest source files
Write-Step "Harvesting source files..."

# Harvest src/ directory
& $Heat dir "$RepoRoot\src" `
    -cg SourceFiles `
    -dr SrcFolder `
    -scom -sfrag -srd -sreg -gg `
    -var var.SourceDir `
    -out "$ObjDir\src-files.wxs"

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to harvest src/ files"
    exit 1
}

# Harvest data/ directory
& $Heat dir "$RepoRoot\data" `
    -cg DataFiles `
    -dr DataFolder `
    -scom -sfrag -srd -sreg -gg `
    -var var.DataDir `
    -out "$ObjDir\data-files.wxs"

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to harvest data/ files"
    exit 1
}

# Harvest ports/ directory
& $Heat dir "$RepoRoot\ports" `
    -cg PortsFiles `
    -dr PortsFolder `
    -scom -sfrag -srd -sreg -gg `
    -var var.PortsDir `
    -out "$ObjDir\ports-files.wxs"

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Failed to harvest ports/ files"
    exit 1
}

Write-Success "Files harvested successfully"

# Compile WiX source files
Write-Step "Compiling WiX sources..."

$WxsFiles = @(
    "$ScriptDir\Product.wxs",
    "$ObjDir\src-files.wxs",
    "$ObjDir\data-files.wxs",
    "$ObjDir\ports-files.wxs"
)

$CandleArgs = @(
    "-dProductVersion=$Version",
    "-dSourceDir=$RepoRoot\src",
    "-dDataDir=$RepoRoot\data",
    "-dPortsDir=$RepoRoot\ports",
    "-arch", "x64",
    "-out", "$ObjDir\",
    "-ext", "WixUIExtension"
) + $WxsFiles

& $Candle @CandleArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Compilation failed"
    exit 1
}

Write-Success "WiX sources compiled"

# Link MSI
Write-Step "Linking MSI installer..."

$WixObjFiles = Get-ChildItem -Path $ObjDir -Filter "*.wixobj" | ForEach-Object { $_.FullName }
$MsiOutput = Join-Path $OutputDir "SecureUSB-$Version-x64.msi"

$LightArgs = @(
    "-out", $MsiOutput,
    "-ext", "WixUIExtension",
    "-cultures:en-US"
) + $WixObjFiles

& $Light @LightArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error-Custom "Linking failed"
    exit 1
}

Write-Success "MSI created successfully"

# Display results
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " Build Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "MSI Installer: $MsiOutput"
Write-Host "Size: $((Get-Item $MsiOutput).Length / 1MB) MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now install SecureUSB by running:"
Write-Host "  msiexec /i ""$MsiOutput""" -ForegroundColor Yellow
Write-Host ""
