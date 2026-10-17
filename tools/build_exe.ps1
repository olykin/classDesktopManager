# Build a single-file x64 Windows executable with PyInstaller.
# NOTE: keep this file ASCII-only (Windows PowerShell 5.1 mis-decodes non-ASCII .ps1).
#
# Usage:
#   powershell -File tools\build_exe.ps1 -Python C:\path\to\python.exe
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$log = Join-Path $root "build\pyinstaller.log"
New-Item -ItemType Directory -Force -Path (Join-Path $root "build") | Out-Null

$args = @(
  "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
  "--name", "classDesktopManager",
  "--icon", (Join-Path $root "src\dsr\assets\app.ico"),
  "--version-file", (Join-Path $root "tools\version_info.txt"),
  "--add-data", ((Join-Path $root "src\dsr\assets") + ";src\dsr\assets"),
  "--paths", (Join-Path $root "src"),
  "--exclude-module", "numpy", "--exclude-module", "pandas",
  "--exclude-module", "matplotlib", "--exclude-module", "scipy",
  "--exclude-module", "openpyxl", "--exclude-module", "lxml",
  "--exclude-module", "docx", "--exclude-module", "pptx",
  "--exclude-module", "pytest", "--exclude-module", "PIL.ImageQt",
  "--exclude-module", "PIL.ImageShow",
  "--distpath", (Join-Path $root "dist"),
  "--workpath", (Join-Path $root "build"),
  "--specpath", (Join-Path $root "build"),
  (Join-Path $root "src\main.py")
)
& $Python @args 2>&1 | Out-File -FilePath $log -Encoding utf8
$code = $LASTEXITCODE
Write-Output "pyinstaller exit=$code  (log: $log)"
if ($code -ne 0) { Get-Content $log -Tail 40; exit $code }

$exe = Join-Path $root "dist\classDesktopManager.exe"
Get-Item $exe | Select-Object FullName, Length, LastWriteTime | Format-List
