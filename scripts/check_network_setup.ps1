$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$script:checks=0
function Verify([bool]$ok,[string]$message){if(-not $ok){throw $message};$script:checks++}
$config=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'config/network_setup.json') | ConvertFrom-Json
$source=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'rovo/network_setup.py')
$service=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'scripts/rovo-network.service')
$tests=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'tests/test_network_setup.py')
Verify ($config.enabled -eq $false) 'Netzwerkdienst muss standardmaessig aus sein'
Verify ($config.grace_seconds -ge 60) 'Verbindungsfrist fehlt'
Verify ($config.activity_timeout_seconds -gt 0) 'Inaktivitaetslimit fehlt'
Verify ($config.retry_seconds -ge 30) 'Fehlerpause fehlt'
Verify ($config.psobject.Properties.Name -notcontains 'password') 'Kein Passwort in Referenzkonfiguration'
foreach($marker in @('if not config["enabled"] or not args.apply:', 'sys.platform != "linux"',
 'os.geteuid() != 0', 'fcntl.LOCK_EX | fcntl.LOCK_NB', 'connected is not False',
 'mode == "infrastructure"', 'stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL',
 'PORTAL_PASSPHRASE', 'metadata.st_uid != 0', '0o077', 'timeout=12',
 '192.168.42.1', '--activity-timeout', 'gate.offline_since = None')){
 Verify (([regex]::Replace($source,'\s','')).Contains([regex]::Replace($marker,'\s',''))) "Vertragsmerkmal fehlt: $marker"
}
Verify (-not $source.Contains('shell=True')) 'Keine Shellausfuehrung'
Verify (-not $source.Contains('--portal-passphrase')) 'Kein Passwort im Prozessargument'
Verify (-not $source.Contains('from .core')) 'Root-Dienst darf Core nicht starten'
Verify ($service.Contains('KillMode=control-group')) 'Kindprozessgruppe muss beendet werden'
Verify ($service.Contains('ProtectHome=true')) 'Getrennte Systempfade erforderlich'
Verify ($service.Contains('--apply')) 'Explizite Startoption fehlt'
Verify (([regex]::Matches($tests,'    def test_')).Count -eq 8) 'Acht WLAN-Testmethoden erwartet'
Write-Output "WLAN: $script:checks statische Vertragspruefungen bestanden. Python-/Pi-Netzwerktests bleiben offen."
