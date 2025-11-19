param(
    [string]$Version = "1.0.0",
    [string]$Platform = "x64",
    [string]$CandleExe = "candle.exe",
    [string]$LightExe = "light.exe",
    [string]$HeatExe = "heat.exe"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$buildDir = Join-Path $scriptDir "build"
$stageDir = Join-Path $buildDir "stage"
$payloadDir = Join-Path $stageDir "SecureUSB"
$wixObjDir = Join-Path $buildDir "obj"
$outDir = Join-Path $scriptDir "dist"

Write-Host "== SecureUSB MSI builder =="
Write-Host "Version: $Version"
Write-Host "Repo:    $repoRoot"

Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item $payloadDir -ItemType Directory -Force | Out-Null
New-Item $outDir -ItemType Directory -Force | Out-Null

Write-Host "--> Staging application files"
robocopy $repoRoot $payloadDir /E /NFL /NDL /NJH /NJS /XD .git packaging\debian\build macos\pkg\build windows\msi\build > $null

Write-Host "--> Creating Windows wrapper scripts"
$binDir = Join-Path $payloadDir "bin"
New-Item $binDir -ItemType Directory -Force | Out-Null

Set-Content -Path (Join-Path $binDir "secureusb-setup.cmd") -Value "@echo off`r`ncd /d ""%~dp0..""`r`npython windows\src\setup_cli.py %*"
Set-Content -Path (Join-Path $binDir "secureusb-windows.cmd") -Value "@echo off`r`ncd /d ""%~dp0..""`r`npython windows\src\app.py %*"

Write-Host "--> Harvesting payload with heat"
$harvestWxs = Join-Path $buildDir "Harvested.wxs"
& $HeatExe dir $payloadDir -nologo -cg SecureUSBFiles -dr INSTALLDIR -var var.PayloadDir -out $harvestWxs -sfrag -srd -ke -gg -g1

Write-Host "--> Running candle"
New-Item $wixObjDir -ItemType Directory -Force | Out-Null
& $CandleExe -nologo `
    -dVersion=$Version `
    -dPayloadDir=$payloadDir `
    -out (Join-Path $wixObjDir "Product.wixobj") `
    (Join-Path $scriptDir "Product.wxs")

& $CandleExe -nologo `
    -dPayloadDir=$payloadDir `
    -out (Join-Path $wixObjDir "Harvested.wixobj") `
    $harvestWxs

Write-Host "--> Running light"
$msiPath = Join-Path $outDir "SecureUSB-$Version.msi"
& $LightExe -nologo `
    -ext WixUIExtension `
    -ext WixUtilExtension `
    -out $msiPath `
    (Join-Path $wixObjDir "Product.wixobj") `
    (Join-Path $wixObjDir "Harvested.wixobj")

Write-Host "✓ MSI created at $msiPath"
