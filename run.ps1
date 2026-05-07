$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Frontend = Join-Path $Root "frontend"
$Runtime = Join-Path $Root ".runtime"

if (!(Test-Path $Python)) {
    py -3 -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $Root "backend\requirements.txt")

if (!(Test-Path (Join-Path $Frontend "node_modules"))) {
    npm --prefix $Frontend install
}

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

$owners = Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($ownerPid in $owners) {
    if ($ownerPid -and $ownerPid -ne $PID) {
        Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
    }
}

$backend = Start-Job -Name "pdf-invitation-backend" -ScriptBlock {
    param($ProjectRoot, $PythonExe)
    Set-Location $ProjectRoot
    & $PythonExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
} -ArgumentList $Root, $Python

$frontend = Start-Job -Name "pdf-invitation-frontend" -ScriptBlock {
    param($ProjectRoot)
    Set-Location $ProjectRoot
    & npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173
} -ArgumentList $Root

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:5173"

Write-Host ""
Write-Host "PDF Invitation Batch Creator is running:"
Write-Host "  Frontend: http://127.0.0.1:5173"
Write-Host "  Backend:  http://127.0.0.1:8000"
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers."

try {
    while ($true) {
        $running = Get-Job -Id $backend.Id, $frontend.Id | Where-Object { $_.State -eq "Running" }
        if ($running.Count -lt 2) {
            Get-Job -Id $backend.Id, $frontend.Id | Receive-Job -Keep
            throw "One of the app servers stopped. Check the output above."
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Stop-Job -Id $backend.Id, $frontend.Id -ErrorAction SilentlyContinue
    Remove-Job -Id $backend.Id, $frontend.Id -Force -ErrorAction SilentlyContinue
    $owners = Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($ownerPid in $owners) {
        if ($ownerPid -and $ownerPid -ne $PID) {
            Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
        }
    }
}
