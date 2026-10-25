# Statische Strukturprüfung. Ersetzt weder Python-Tests noch Firmware-Build.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$checked = 0
function Check([bool]$Condition, [string]$Description) {
    if (-not $Condition) { throw "FEHLER: $Description" }
    Write-Output "OK: $Description"
    $script:checked++
}
$config = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'config/default.json') | ConvertFrom-Json
Check ($config.safe_mode -eq $true -and $config.simulation -eq $true) 'Safe Mode und Simulation standardmäßig aktiv'
Check ($config.motion.calibrated -eq $false) 'Keine erfundene Kalibrierung'
Check ($null -eq $config.motion.pan.home -and $null -eq $config.motion.tilt.home) 'Keine historischen Home-Werte übernommen'
$flow = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'nodered/rovo_neu_flows.json') | ConvertFrom-Json
$flowIds = @{}
foreach ($node in $flow) {
    Check (-not $flowIds.ContainsKey($node.id)) "Eindeutige Node-ID $($node.id)"
    $flowIds[$node.id] = $true
}
foreach ($node in $flow) {
    foreach ($link in $node.links) { Check ($flowIds.ContainsKey($link)) "Link-Ziel $link vorhanden" }
    foreach ($wireGroup in $node.wires) {
        foreach ($wire in $wireGroup) { Check ($flowIds.ContainsKey($wire)) "Wire-Ziel $wire vorhanden" }
    }
    foreach ($property in @('z','ui','page','group','theme')) {
        $reference = $node.$property
        if ($reference) { Check ($flowIds.ContainsKey($reference)) "Konfigurationsreferenz $reference vorhanden" }
    }
}
Check (@($flow | Where-Object type -eq 'ui-base').Count -eq 1) 'Genau eine neue UI-Base'
Check (@($flow | Where-Object type -eq 'ui-page').Count -eq 9) 'Neun erhaltene V5-Dashboardseiten'
$overview = $flow | Where-Object id -eq 'd02026bb00003000'
Check (-not $overview.format.Contains('motion.relative')) 'Keine Direktbewegung auf Übersicht'
Check (@($flow | Where-Object type -eq 'exec').Count -eq 0) 'Kein konkurrierender alter Host-Exec'
Check (@($flow | Where-Object type -eq 'mqtt out').Count -eq 1) 'Ein gemeinsamer MQTT-Befehlspfad'
Check (@($flow | Where-Object type -eq 'mqtt in').Count -eq 1) 'MQTT-Antworten und Status vorhanden'
$base = $flow | Where-Object type -eq 'ui-base'
Check ($base.path -eq '/rovo') 'V5-URL erhalten'
Check ($base.includeClientData -and $base.acceptsClientConfig -contains 'ui-template') 'Antworten an Dashboard-Client gebunden'
$reference = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'nodered/ROVO_V5_original.json') | ConvertFrom-Json
Check (($flow | Where-Object type -eq 'ui-theme' | ConvertTo-Json -Depth 20 -Compress) -eq ($reference | Where-Object type -eq 'ui-theme' | ConvertTo-Json -Depth 20 -Compress)) 'V5-Theme unverändert'
$originalStyle = $reference | Where-Object id -eq 'd02026bb00000003'
$adaptedStyle = $flow | Where-Object id -eq 'd02026bb00000003'
Check ($originalStyle.format -eq $adaptedStyle.format) 'V5-CSS unverändert'
foreach ($page in ($reference | Where-Object type -eq 'ui-page')) {
    $adaptedPage = $flow | Where-Object id -eq $page.id
    Check ($adaptedPage.path -eq $page.path -and $adaptedPage.name -eq $page.name) "V5-Seite $($page.name) erhalten"
}
foreach ($widget in ($flow | Where-Object { $_.type -eq 'ui-template' -and $_.templateScope -eq 'local' })) {
    Check ($widget.format.Contains('bridgeFresh') -and -not $widget.format.Contains('mixins:')) "FlowFuse-kompatible Verbindungsanzeige auf $($widget.name)"
    Check (-not $widget.passthru -and -not $widget.storeOutMessages -and -not $widget.resendOnRefresh) "Keine Rückkopplung oder Befehlswiederholung: $($widget.name)"
}
$firmware = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'esp32/rovo_esp32/rovo_esp32.ino')
$calibration = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'esp32/rovo_esp32/calibration.h')
Check ($calibration.Contains('#define ROVO_ENABLE_SERVOS 0')) 'Firmware: PWM ab Werk abgeschaltet'
Check ($calibration.Contains('#define ROVO_CALIBRATED 0')) 'Firmware: keine Kalibrierung behauptet'
Check ($firmware.Contains('PAN_GPIO = 18') -and $firmware.Contains('TILT_GPIO = 17')) 'Historische Signal-GPIOs erhalten'
Check (-not [regex]::IsMatch($firmware, '\bdelay\s*\(')) 'Keine blockierenden delay-Aufrufe in Firmware'
Check ($firmware.Contains('WATCHDOG_MS') -and $firmware.Contains('OUT_OF_RANGE')) 'Watchdog und Firmware-Grenzprüfung vorhanden'
$pythonFiles = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'rovo') -Filter '*.py' -File -Recurse)
Check ($pythonFiles.Count -ge 15) 'Python-Module vollständig abgelegt'
foreach ($file in $pythonFiles) {
    $code = Get-Content -Raw -Encoding UTF8 -LiteralPath $file.FullName
    Check (-not [regex]::IsMatch($code, '(?m)^\s*(?:return\s+)?(?:eval|exec)\s*\(')) "Kein direkter eval/exec-Aufruf: $($file.Name)"
}
Write-Output "STATISCHE PRÜFUNG: $checked Prüfungen bestanden. Python-/Arduino-/Node-RED-Laufzeittests sind separat erforderlich."
