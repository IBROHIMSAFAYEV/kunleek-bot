# Bot va admin panelni shu kompyuterda fon rejimida ishlatadi; biri to'xtasa, qayta yoqadi.
# Windows'ga kirilganda avtomatik ishga tushadi (Startup papkasidagi korzinka_bot.cmd orqali).
Set-Location $PSScriptRoot
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$supLog = Join-Path $logDir "supervisor.log"

# eski nusxalarni to'xtatamiz: bitta token bilan ikkita bot ishlay olmaydi
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -match 'run_local\.ps1' -and $_.ProcessId -ne $PID } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'manage\.py (runbot|runserver)' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# setup_windows.ps1 yaratgan venv bo'lsa — o'shani, bo'lmasa tizimdagi Python
$venvPy = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$python = if (Test-Path $venvPy) { $venvPy } else { (Get-Command python).Source }
$jobs = @{
    bot   = @("manage.py", "runbot")
    admin = @("manage.py", "runserver", "127.0.0.1:8000", "--noreload")
}
$procs = @{}
while ($true) {
    foreach ($name in $jobs.Keys) {
        if (-not $procs[$name] -or $procs[$name].HasExited) {
            Add-Content $supLog "$(Get-Date -Format s) $name ishga tushirildi"
            $procs[$name] = Start-Process $python -ArgumentList $jobs[$name] -WorkingDirectory $PSScriptRoot `
                -RedirectStandardError (Join-Path $logDir "$name.log") `
                -RedirectStandardOutput (Join-Path $logDir "$name.out.log") -PassThru -WindowStyle Hidden
        }
    }
    Start-Sleep 15
}
