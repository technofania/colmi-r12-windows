<#
    skroty.ps1 - robi (albo kasuje) dwa skroty na pulpicie uzytkownika.

    Celowo tylko na pulpicie biezacego uzytkownika: zadnego wpisu w
    rejestrze, zadnego Program Files, zadnego UAC. Paczka ma dzialac
    na komputerze studenta bez praw administratora.

    Uzycie:
        powershell -File skroty.ps1 -Korzen "C:\...\colmi-r12-windows"
        powershell -File skroty.ps1 -Usun
#>

param(
    [string]$Korzen,
    [switch]$Usun
)

$ErrorActionPreference = 'Stop'

$pulpit = [Environment]::GetFolderPath('Desktop')
$nazwy = @(
    'Pierscien R12 - strumien do TouchDesignera',
    'Pierscien R12 - projekt TouchDesigner'
)

if ($Usun) {
    foreach ($n in $nazwy) {
        $p = Join-Path $pulpit ($n + '.lnk')
        if (Test-Path $p) {
            Remove-Item $p -Force
            Write-Host "   skasowany skrot: $n"
        }
    }
    exit 0
}

if (-not $Korzen) { $Korzen = Split-Path -Parent $PSScriptRoot }
if (-not (Test-Path $Korzen)) {
    Write-Host "   nie ma folderu $Korzen - pomijam skroty"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell

function Nowy-Skrot {
    param($Nazwa, $Cel, $Opis)
    if (-not (Test-Path $Cel)) {
        Write-Host "   brak $Cel - pomijam skrot '$Nazwa'"
        return
    }
    $lnk = $shell.CreateShortcut((Join-Path $pulpit ($Nazwa + '.lnk')))
    $lnk.TargetPath = $Cel
    $lnk.WorkingDirectory = $Korzen
    $lnk.Description = $Opis
    $lnk.Save()
    Write-Host "   skrot: $Nazwa"
}

Nowy-Skrot -Nazwa $nazwy[0] `
    -Cel (Join-Path $Korzen 'URUCHOM.bat') `
    -Opis 'Laczy sie z pierscieniem COLMI R12 i wysyla dane przez OSC do TouchDesignera'

Nowy-Skrot -Nazwa $nazwy[1] `
    -Cel (Join-Path $Korzen 'td\RING_START.toe') `
    -Opis 'Gotowy projekt TouchDesignera odbierajacy dane z pierscienia'

exit 0
