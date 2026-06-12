# ============================================================================
#  Installateur guidé — App Gestion (centre social)
#  Usage : clic droit sur ce fichier -> "Exécuter avec PowerShell"
#  Ce script installe TOUT : Python, PostgreSQL, l'application,
#  le service Windows (démarrage automatique) et la sauvegarde quotidienne.
# ============================================================================
$ErrorActionPreference = "Stop"

# --- 0. Élévation administrateur -------------------------------------------
$estAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $estAdmin) {
    Write-Host "Demande des droits administrateur..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

function Etape($texte) { Write-Host "`n=== $texte ===" -ForegroundColor Cyan }
function Ok($texte)    { Write-Host "  [OK] $texte" -ForegroundColor Green }
function Info($texte)  { Write-Host "  $texte" }

function MotDePasseAleatoire([int]$longueur = 24) {
    $alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    -join (1..$longueur | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
}

Write-Host ""
Write-Host "+--------------------------------------------------------------+" -ForegroundColor Cyan
Write-Host "¦      INSTALLATION DE L'APPLICATION DE GESTION                  ¦" -ForegroundColor Cyan
Write-Host "¦  Répondez aux questions (Entrée = choix par défaut).          ¦" -ForegroundColor Cyan
Write-Host "¦  L'installation prend 10 à 20 minutes selon la connexion.     ¦" -ForegroundColor Cyan
Write-Host "+--------------------------------------------------------------+" -ForegroundColor Cyan

# --- 1. Questions -----------------------------------------------------------
Etape "1/8 - Questions de configuration"

$dossierDefaut = "C:\AppGestion"
$dossier = Read-Host "Dossier d'installation [$dossierDefaut]"
if ([string]::IsNullOrWhiteSpace($dossier)) { $dossier = $dossierDefaut }

$portDefaut = "8000"
$port = Read-Host "Port de l'application [$portDefaut]"
if ([string]::IsNullOrWhiteSpace($port)) { $port = $portDefaut }

$reseau = Read-Host "L'application doit-elle être accessible depuis d'autres postes du réseau ? (o/N)"
$hote = "127.0.0.1"
if ($reseau -match "^[oO]") { $hote = "0.0.0.0" }

$pgPortDefaut = "5432"
$pgPort = Read-Host "Port PostgreSQL [$pgPortDefaut]"
if ([string]::IsNullOrWhiteSpace($pgPort)) { $pgPort = $pgPortDefaut }

$mdpSuper = MotDePasseAleatoire
$mdpApp = MotDePasseAleatoire
$reponse = Read-Host "Mot de passe de la base de données (Entrée = généré automatiquement)"
if (-not [string]::IsNullOrWhiteSpace($reponse)) { $mdpApp = $reponse }

# --- 2. Python --------------------------------------------------------------
Etape "2/8 - Python"
$python = Get-Command python -ErrorAction SilentlyContinue
$pythonOk = $false
if ($python) {
    $version = & python --version 2>&1
    if ($version -match "Python 3\.(1[1-9]|[2-9][0-9])") { $pythonOk = $true; Ok "$version déjà installé" }
}
if (-not $pythonOk) {
    Info "Installation de Python 3.13 (winget)..."
    winget install --id Python.Python.3.13 --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Échec de l'installation de Python. Installez-le depuis python.org puis relancez ce script." }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    Ok "Python installé"
}

# --- 3. PostgreSQL ----------------------------------------------------------
Etape "3/8 - PostgreSQL"
$psql = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
if ($psql) {
    Ok "PostgreSQL déjà installé : $($psql.FullName)"
    $mdpSuper = Read-Host "Mot de passe du super-utilisateur 'postgres' existant"
} else {
    Info "Installation de PostgreSQL 16 (winget)... (plusieurs minutes)"
    winget install --id PostgreSQL.PostgreSQL.16 --silent --accept-package-agreements --accept-source-agreements --override "--mode unattended --unattendedmodeui none --superpassword $mdpSuper --serverport $pgPort"
    if ($LASTEXITCODE -ne 0) { throw "Échec de l'installation de PostgreSQL. Voir LISEZMOI-INSTALLATION.md, section Dépannage." }
    $psql = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\psql.exe" | Sort-Object FullName -Descending | Select-Object -First 1
    Ok "PostgreSQL installé : $($psql.FullName)"
}

Info "Création de la base de données de l'application..."
$env:PGPASSWORD = $mdpSuper
$sql = @"
DO `$`$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'appgestion') THEN
    CREATE ROLE appgestion LOGIN PASSWORD '$mdpApp';
  ELSE
    ALTER ROLE appgestion WITH LOGIN PASSWORD '$mdpApp';
  END IF;
END `$`$;
"@
& $psql.FullName -U postgres -h 127.0.0.1 -p $pgPort -v ON_ERROR_STOP=1 -c $sql | Out-Null
$existe = & $psql.FullName -U postgres -h 127.0.0.1 -p $pgPort -tAc "SELECT 1 FROM pg_database WHERE datname='appgestion'"
if ($existe -ne "1") {
    & $psql.FullName -U postgres -h 127.0.0.1 -p $pgPort -v ON_ERROR_STOP=1 -c "CREATE DATABASE appgestion OWNER appgestion ENCODING 'UTF8'" | Out-Null
}
Remove-Item Env:PGPASSWORD
Ok "Base 'appgestion' prête (utilisateur 'appgestion')"

# --- 4. Copie de l'application ----------------------------------------------
Etape "4/8 - Copie de l'application"
$source = Split-Path -Parent $PSScriptRoot   # le script est dans <app>\installation\
New-Item -ItemType Directory -Force -Path $dossier | Out-Null
robocopy $source $dossier /E /XD .git .venv __pycache__ instance /XF .env /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Échec de la copie des fichiers (robocopy: $LASTEXITCODE)" }
Ok "Fichiers copiés vers $dossier"

# --- 5. Environnement Python -------------------------------------------------
Etape "5/8 - Dépendances Python (plusieurs minutes)"
Set-Location $dossier
if (-not (Test-Path "$dossier\.venv")) { python -m venv .venv }
& "$dossier\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& "$dossier\.venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { throw "Échec de l'installation des dépendances Python." }
Ok "Dépendances installées"

# --- 6. Configuration (.env) -------------------------------------------------
Etape "6/8 - Configuration"
$secretKey = MotDePasseAleatoire 64
$urlPublique = "http://$(if ($hote -eq '0.0.0.0') { $env:COMPUTERNAME } else { '127.0.0.1' }):$port"
@"
# Fichier généré par l'installateur le $(Get-Date -Format "yyyy-MM-dd HH:mm")
# NE PAS PARTAGER : contient les mots de passe de l'application.
ERP_ENV=production
SECRET_KEY=$secretKey
DATABASE_URL=postgresql://appgestion:$mdpApp@127.0.0.1:$pgPort/appgestion
ERP_HOST=$hote
ERP_PORT=$port
ERP_THREADS=12
ERP_PUBLIC_BASE_URL=$urlPublique
DB_AUTO_UPGRADE_ON_START=1
PASSWORD_RESET_ALLOW_DEBUG_LINK=0
"@ | Set-Content -Path "$dossier\.env" -Encoding UTF8
Ok "Configuration écrite dans $dossier\.env"

# --- 7. Service Windows (démarrage automatique) ------------------------------
Etape "7/8 - Service Windows"
$nssm = "$dossier\tools\nssm\win64\nssm.exe"
if (-not (Test-Path $nssm)) {
    Info "Téléchargement de NSSM (gestionnaire de service)..."
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath "$env:TEMP\nssm-extract" -Force
    New-Item -ItemType Directory -Force -Path "$dossier\tools\nssm\win64" | Out-Null
    Copy-Item "$env:TEMP\nssm-extract\nssm-2.24\win64\nssm.exe" $nssm -Force
}
New-Item -ItemType Directory -Force -Path "$dossier\logs" | Out-Null
$serviceExiste = Get-Service -Name "AppGestion" -ErrorAction SilentlyContinue
if ($serviceExiste) {
    & $nssm stop AppGestion 2>$null | Out-Null
    & $nssm remove AppGestion confirm | Out-Null
}
& $nssm install AppGestion "$dossier\.venv\Scripts\python.exe" "$dossier\run_waitress.py" | Out-Null
& $nssm set AppGestion AppDirectory $dossier | Out-Null
& $nssm set AppGestion Start SERVICE_AUTO_START | Out-Null
& $nssm set AppGestion AppStdout "$dossier\logs\service-out.log" | Out-Null
& $nssm set AppGestion AppStderr "$dossier\logs\service-err.log" | Out-Null
& $nssm start AppGestion | Out-Null
Ok "Service 'AppGestion' installé (démarre automatiquement avec Windows)"

if ($hote -eq "0.0.0.0") {
    netsh advfirewall firewall delete rule name="AppGestion" 2>$null | Out-Null
    netsh advfirewall firewall add rule name="AppGestion" dir=in action=allow protocol=TCP localport=$port | Out-Null
    Ok "Pare-feu ouvert sur le port $port (accès réseau local)"
}

# Sauvegarde quotidienne (2h du matin)
if (Test-Path "$dossier\tools\backup_instance.py") {
    schtasks /Create /F /TN "AppGestion-Sauvegarde" /SC DAILY /ST 02:00 /RU SYSTEM `
        /TR "`"$dossier\.venv\Scripts\python.exe`" `"$dossier\tools\backup_instance.py`"" | Out-Null
    Ok "Sauvegarde quotidienne programmée (2h00)"
}

# --- 8. Vérification ----------------------------------------------------------
Etape "8/8 - Vérification du démarrage"
$pret = $false
foreach ($i in 1..24) {
    Start-Sleep -Seconds 5
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/healthz" -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) { $pret = $true; break }
    } catch { Info "L'application démarre... ($i/24)" }
}

Write-Host ""
if ($pret) {
    Write-Host "+--------------------------------------------------------------+" -ForegroundColor Green
    Write-Host "¦  INSTALLATION TERMINÉE AVEC SUCCÈS                             ¦" -ForegroundColor Green
    Write-Host "+--------------------------------------------------------------+" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Adresse de l'application : $urlPublique" -ForegroundColor White
    Write-Host "  Dossier d'installation   : $dossier"
    Write-Host "  Journal des erreurs      : $dossier\instance\logs\erreurs.log"
    Write-Host "  Configuration            : $dossier\.env  (à conserver précieusement)"
    if (-not $serviceExiste -and -not $psql) {
        Write-Host "  Mot de passe 'postgres'  : $mdpSuper  (NOTEZ-LE)" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "  Le navigateur va s'ouvrir : créez votre compte administrateur." -ForegroundColor Cyan
    Start-Process "http://127.0.0.1:$port/setup/"
} else {
    Write-Host "L'application n'a pas répondu à temps." -ForegroundColor Red
    Write-Host "Consultez $dossier\logs\service-err.log et la section Dépannage du LISEZMOI." -ForegroundColor Red
}
Write-Host ""
Read-Host "Appuyez sur Entrée pour fermer"
