param([switch]$GerarExe)
# Native Python errors must reach the exit-code checks, not terminate discovery.
$ErrorActionPreference = 'Continue'
Set-Location -LiteralPath $PSScriptRoot
function Find-Python {
    $candidates = @("$env:LOCALAPPDATA\Programs\Python\Python313\python.exe")
    foreach ($name in @('python', 'py')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) { $candidates += $command.Source }
    }
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try {
            $result = & $candidate -c 'import sys, tkinter; assert sys.version_info >= (3,9); print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $result) { return ($result | Select-Object -Last 1) }
        } catch { }
    }
    return $null
}
try {
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $python = Find-Python
        if (-not $python) {
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
                throw 'Instale o Atualizador de Aplicativo da Microsoft Store (winget), ou Python em https://www.python.org/downloads/windows/ com Tcl/Tk, e abra ABRIR.bat novamente.'
            }
            Write-Host 'Instalando Python para seu usuario. Aguarde...'
            & winget install --id Python.Python.3.13 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
            $python = Find-Python
            if (-not $python) { throw 'Python nao foi localizado. Confira a mensagem de instalacao acima e abra ABRIR.bat novamente.' }
        }
        & $python -m venv (Join-Path $PSScriptRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar o ambiente do aplicativo.' }
    }
    & $venvPython -c 'import tkinter, pyautogui, win32gui, win32con' 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Instalando dependencias. Internet necessaria na primeira abertura...'
        & $venvPython -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Falha nas dependencias. Verifique sua conexao e tente novamente.' }
        & $venvPython -c 'import tkinter, pyautogui, win32gui, win32con'
        if ($LASTEXITCODE -ne 0) { throw 'As dependencias nao passaram na verificacao.' }
    }
    if ($GerarExe) {
        & $venvPython -m pip install pyinstaller
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel instalar PyInstaller.' }
        & $venvPython -m PyInstaller --noconfirm --clean --onefile --windowed --name N2 (Join-Path $PSScriptRoot 'pausa_automatica.py')
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o executavel.' }
        Write-Host "Pronto: $PSScriptRoot\dist\N2.exe"
        Write-Host 'Copie N2.exe para outro computador Windows sem instalar Python.'
    } else {
        & $venvPython (Join-Path $PSScriptRoot 'pausa_automatica.py')
        if ($LASTEXITCODE -ne 0) { throw 'O aplicativo encerrou com erro. Confira a mensagem acima.' }
    }
    exit 0
} catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
