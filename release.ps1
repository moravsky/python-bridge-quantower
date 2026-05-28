$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

# Version from the latest git tag
if (-not (git tag --list)) {
    Write-Error "No git tags found. Tag a version first (e.g. 'git tag v1.0.0')."
    exit 1
}
$version = (git describe --tags --abbrev=0).Trim()

# Quantower version from the csproj's QT_Path
$csproj = Get-Content "$root\PythonBridgeQuantower\PythonBridgeQuantower.csproj" -Raw
if ($csproj -notmatch '<QT_Path>[^<]*\\v([\d\.]+)</QT_Path>') {
    Write-Error "Could not extract Quantower version from csproj QT_Path."
    exit 1
}
$qtVersion = $matches[1]

Write-Host "Packaging $version against Quantower v$qtVersion"

# Build Release
dotnet build "$root\PythonBridgeQuantower\PythonBridgeQuantower.csproj" -c Release
if ($LASTEXITCODE -ne 0) {
    Write-Error "Build failed."
    exit 1
}

# Stage files in a temp folder
$artifacts = "$root\artifacts"
$stage = "$artifacts\stage"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# Strategy DLL + deps + pdb
$stratDest = "$stage\PythonBridgeQuantower"
New-Item -ItemType Directory -Force -Path $stratDest | Out-Null
$buildOut = "$root\PythonBridgeQuantower\bin\Release"
Copy-Item "$buildOut\PythonBridgeQuantower.dll" $stratDest
Copy-Item "$buildOut\PythonBridgeQuantower.deps.json" $stratDest
Copy-Item "$buildOut\PythonBridgeQuantower.pdb" $stratDest

# Python TUI
$tuiDest = "$stage\tui"
New-Item -ItemType Directory -Force -Path $tuiDest | Out-Null
Copy-Item "$root\tui\tape.py" $tuiDest

# Top-level files
Copy-Item "$root\requirements.txt" $stage
Copy-Item "$root\README.md" $stage

# Zip
$zipName = "python-bridge-quantower-$version-qt$qtVersion.zip"
$zipPath = "$artifacts\$zipName"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$stage\*" -DestinationPath $zipPath

# Cleanup stage
Remove-Item $stage -Recurse -Force

Write-Host "Created: $zipPath"
