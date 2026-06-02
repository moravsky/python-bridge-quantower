# One-command install of PythonBridgeQuantower from this release package.
#
# Build-free: copies the prebuilt strategy DLLs (in this package's
# PythonBridgeQuantower folder) into Quantower's Strategies folder, then
# installs the Python TUI's dependencies. No .NET SDK needed. Run from the
# unzipped release package. After it finishes, only one manual step remains:
# add and start the strategy in Quantower (a GUI action).
#
# (Developers building from source use deploy.ps1 instead, which compiles.)
#
#   .\install.ps1                          # default Quantower at C:\Quantower
#   .\install.ps1 -QuantowerPath D:\Quantower
#   .\install.ps1 -Python py               # use a different Python launcher
#   .\install.ps1 -SkipPython              # strategy only, manage deps yourself

param(
    [string]$QuantowerPath = "C:\Quantower",
    [string]$Python = "python",
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$source = Join-Path $root "PythonBridgeQuantower"

# The prebuilt DLLs ship in this package's PythonBridgeQuantower folder.
if (-not (Test-Path $source) -or
    -not (Get-ChildItem -Path $source -Filter *.dll -ErrorAction SilentlyContinue)) {
    Write-Error "No prebuilt strategy DLLs in '$source'. Run this from the unzipped release package (developers build from source with deploy.ps1)."
    exit 1
}

if (-not (Test-Path $QuantowerPath)) {
    Write-Error "Quantower not found at '$QuantowerPath'. Pass the install dir: .\install.ps1 -QuantowerPath <dir>"
    exit 1
}

$dest = Join-Path $QuantowerPath "Settings\Scripts\Strategies\PythonBridgeQuantower"

# Guard: only ever touch our own strategy folder.
if ($dest -notmatch "Quantower.*PythonBridgeQuantower$") {
    Write-Error "Destination path doesn't look right: $dest. Aborting."
    exit 1
}

# Clean the destination so stale assemblies never linger.
if (Test-Path $dest) {
    Write-Host "Cleaning $dest"
    Remove-Item "$dest\*" -Force -Recurse
} else {
    Write-Host "Creating $dest"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
}

foreach ($pattern in @("*.dll", "*.pdb", "*.deps.json")) {
    foreach ($item in Get-ChildItem -Path $source -Filter $pattern) {
        Copy-Item $item.FullName -Destination $dest -Force
        Write-Host "Installed: $($item.Name)"
    }
}
Write-Host "Strategy installed to $dest"

# Python TUI dependencies (textual, pyzmq, protobuf).
$req = Join-Path $root "requirements.txt"
if ($SkipPython) {
    Write-Host "Skipping Python deps (-SkipPython)."
} elseif (-not (Test-Path $req)) {
    Write-Warning "requirements.txt not found; skipping Python deps."
} elseif (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Warning "Python ('$Python') not on PATH; skipping deps. Install Python 3.10+ then run: $Python -m pip install -r requirements.txt"
} else {
    Write-Host ""
    Write-Host "Installing Python deps ($Python -m pip install -r requirements.txt)"
    & $Python -m pip install -r $req
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pip install failed -- run it manually: $Python -m pip install -r requirements.txt"
    }
}

Write-Host ""
Write-Host "Done. One manual step left: in Quantower, add the 'PythonBridgeQuantower'"
Write-Host "strategy, pick a symbol, and start it. Then run the TUI:"
Write-Host "  cd tui"
Write-Host "  $Python tape.py"
