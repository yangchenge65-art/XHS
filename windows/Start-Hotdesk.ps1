param([switch]$InstallOnly)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$server = $null

function Find-Python {
    $candidates = @(
        @{ Command = 'py'; Arguments = @('-3.12') },
        @{ Command = 'py'; Arguments = @('-3') },
        @{ Command = 'python'; Arguments = @() }
    )
    $localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (Test-Path -LiteralPath $localPython) {
        $candidates += @{ Command = $localPython; Arguments = @() }
    }
    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) { continue }
        try {
            $arguments = $candidate.Arguments
            $path = & $candidate.Command @arguments -c "import sys; sys.exit(1) if sys.version_info < (3,12) else print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $path) { return ([string]($path | Select-Object -Last 1)).Trim() }
        } catch { continue }
    }
    return $null
}

function Test-Readiness {
    try {
        $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/status' -TimeoutSec 2
        return ($response.budget -eq 30 -and $null -ne $response.sources.douyin -and $null -ne $response.sources.xiaohongshu)
    } catch { return $false }
}

try {
    Write-Host ''
    Write-Host 'Hotdesk - Windows setup and launcher' -ForegroundColor Green
    Write-Host 'First launch needs Internet access for Python packages. No paid API calls are enabled by this installer.'
    $python = Find-Python
    if (-not $python) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host 'Python 3.12+ was not found. Installing Python 3.12 for the current Windows user...'
            & winget install --id Python.Python.3.12 --exact --source winget --scope user --accept-source-agreements --accept-package-agreements --disable-interactivity
            if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Install Python 3.12+ from https://www.python.org/downloads/windows/ and retry.' }
            $python = Find-Python
        }
        if (-not $python) {
            Start-Process 'https://www.python.org/downloads/windows/'
            throw 'Install Python 3.12 or newer from the official page, then double-click Start.bat again.'
        }
    }
    $venvPython = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'Creating a project-local Python environment...'
        & $python -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Cannot create .venv. Extract the ZIP into a writable folder and retry.' }
    }
    $requirements = Join-Path $root 'requirements.txt'
    $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $requirements).Hash
    $stamp = Join-Path $root '.venv\hotdesk-requirements.sha256'
    $installed = (Test-Path -LiteralPath $stamp) -and ((Get-Content -LiteralPath $stamp -Raw).Trim() -eq $digest)
    if (-not $installed -or $InstallOnly) {
        Write-Host 'Installing verified HTTPS packages. Please wait...'
        & $venvPython -m pip install --disable-pip-version-check -r $requirements
        if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check the Internet connection and retry; TLS verification has not been disabled.' }
        & $venvPython -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
        & $venvPython -c "from zoneinfo import ZoneInfo; import flask, openpyxl; print('Timezone ready:', ZoneInfo('Asia/Shanghai'))"
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency check failed.' }
        Set-Content -LiteralPath $stamp -Value $digest -Encoding ASCII
    }
    if ($InstallOnly) { exit 0 }
    if (Test-Readiness) {
        Write-Host 'Hotdesk is already running. Opening the browser...'
        Start-Process 'http://127.0.0.1:8000'
        exit 0
    }
    # Always local-only. Do not inherit a public bind address or a different port.
    $env:HOTDESK_HOST = '127.0.0.1'
    $env:PORT = '8000'
    Write-Host 'Starting Hotdesk. Keep this window open; press Ctrl+C to stop.' -ForegroundColor Green
    $server = Start-Process -FilePath $venvPython -ArgumentList @('run.py') -WorkingDirectory $root -NoNewWindow -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        $server.Refresh()
        if ($server.HasExited) { throw 'The server stopped. Check the error above; port 8000 may already be in use.' }
        if (Test-Readiness) { $ready = $true; break }
    }
    if (-not $ready) { throw 'Server readiness check timed out. Check the error above and retry.' }
    Start-Process 'http://127.0.0.1:8000'
    Write-Host 'Ready. Enable the demo-data switch on the page to try the workflow.'
    Wait-Process -Id $server.Id
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($null -ne $server) {
        $server.Refresh()
        if (-not $server.HasExited) { Stop-Process -Id $server.Id -ErrorAction SilentlyContinue }
    }
}
