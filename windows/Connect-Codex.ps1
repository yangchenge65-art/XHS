$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function Find-Node {
    $command = Get-Command node -ErrorAction SilentlyContinue
    $candidates = @()
    if ($command) { $candidates += $command.Source }
    $candidates += (Join-Path $env:ProgramFiles 'nodejs\node.exe')
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\nodejs\node.exe')
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            & $candidate -e "process.exit(parseInt(process.versions.node) >= 22 ? 0 : 1)"
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

try {
    Write-Host 'Connect Hotdesk to your ChatGPT subscription via the official Codex CLI.' -ForegroundColor Green
    Write-Host 'This may install Node.js and a project-local copy of Codex. It does not purchase API credits.'
    $node = Find-Node
    if (-not $node) {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host 'Installing Node.js LTS. Windows may ask you to approve the installer.'
            & winget install --id OpenJS.NodeJS.LTS --exact --source winget --accept-source-agreements --accept-package-agreements --disable-interactivity
            if ($LASTEXITCODE -ne 0) { throw 'Node.js installation failed. Install Node.js LTS from https://nodejs.org/ and retry.' }
            $node = Find-Node
        }
        if (-not $node) {
            Start-Process 'https://nodejs.org/en/download'
            throw 'Install Node.js LTS (22+) from the official page, then retry Connect-Codex.bat.'
        }
    }
    $npm = Join-Path (Split-Path -Parent $node) 'npm.cmd'
    if (-not (Test-Path -LiteralPath $npm)) { throw 'npm.cmd was not found next to Node.js. Reinstall Node.js LTS.' }
    $prefix = Join-Path $root '.tools\codex'
    $script = Join-Path $prefix 'node_modules\@openai\codex\bin\codex.js'
    $package = Join-Path $prefix 'node_modules\@openai\codex\package.json'
    $installed = $false
    if (Test-Path -LiteralPath $package) {
        $installed = ((Get-Content -LiteralPath $package -Raw | ConvertFrom-Json).version -eq '0.163.0')
    }
    if (-not $installed -or -not (Test-Path -LiteralPath $script)) {
        Write-Host 'Installing pinned official @openai/codex@0.163.0 with npm integrity checks...'
        & $npm install --prefix $prefix --cache (Join-Path $root '.tools\npm-cache') --no-audit --no-fund --ignore-scripts '@openai/codex@0.163.0'
        if ($LASTEXITCODE -ne 0) { throw 'Codex installation failed. Check Internet access; package verification has not been disabled.' }
    }
    & $node $script --version
    if ($LASTEXITCODE -ne 0) { throw 'Codex cannot run on this Windows installation. Keep the error above for troubleshooting.' }
    Write-Host 'The official CLI will open your browser. Sign in with ChatGPT, not an API key.' -ForegroundColor Green
    Write-Host 'Login credentials stay in the official Codex credential store. Hotdesk does not read or copy them.'
    & $node $script login
    if ($LASTEXITCODE -ne 0) { throw 'Login did not complete. Retry Connect-Codex.bat when ready.' }
    & $node $script login status
    if ($LASTEXITCODE -ne 0) { throw 'Login status could not be confirmed.' }
    Write-Host 'Return to Hotdesk, select the Codex subscription mode, refresh status, then generate your daily selection.' -ForegroundColor Green
    Write-Host 'Your plan controls available models and usage limits. Web search and native Windows execution still need a real test.'
} catch {
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Read-Host 'Press Enter to close'
    exit 1
}
