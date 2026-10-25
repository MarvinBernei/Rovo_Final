# Statische Vertragsprüfung. Keine Kamera, Modelle oder Python-Ausführung.
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$checks=0
function Verify([bool]$valid,[string]$message){if(-not $valid){throw $message};$script:checks++}
$catalog=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'rovo/catalog.json') | ConvertFrom-Json
Verify ($catalog.schema_version -eq 1) 'Katalogschema'
$seen=@{}
$phrases=0
$safe=@('stop','cancel','tracking.disable','camera.disable','privacy.enable','llm.disable')
foreach($entry in $catalog.intents){
    Verify ([bool]$entry.intent -and $entry.phrases.Count -gt 0) 'Leere Kataloggruppe'
    Verify ($entry.risk -in @('low','medium','high')) 'Risikoklasse fehlt'
    Verify ($entry.negation_safe -is [bool]) 'Negationsmetadaten fehlen'
    if($entry.negation_safe){Verify ($entry.intent -in $safe) 'Unzulaessige Negationsausnahme'}
    foreach($phrase in $entry.phrases){
        $normalized=[regex]::Replace($phrase.ToLowerInvariant(),'[,.!?;:]',' ')
        $normalized=[regex]::Replace($normalized,'\s+',' ').Trim()
        $normalized=[regex]::Replace($normalized,'^(?:hey\s+)?rovo\s*|\s+rovo$','')
        $normalized=[regex]::Replace($normalized,'^bitte\s+|\s+bitte$','').Trim()
        Verify (-not $seen.ContainsKey($normalized)) "Doppelte Formulierung: $normalized"
        $seen[$normalized]=$true
        $phrases++
    }
}
Verify ($phrases -ge 400) 'Katalogumfang'
$config=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'config/default.json') | ConvertFrom-Json
Verify ($config.people.enabled -eq $false) 'Keine automatische Kamera-/Modellaktivierung'
Verify ($config.people.recognition_verified -eq $false) 'Keine ungepruefte Wiedererkennungsfreigabe'
Verify ($config.people.store_images -eq $false) 'Bildspeicherung standardmaessig aus'
Verify ($config.people.samples_per_pose -eq 40) '200 Zielansichten ueber fuenf Posen'
$people=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'rovo/people.py')
foreach($marker in @('WAIT_NAME','WAIT_CONSENT','CAPTURING','ON DELETE CASCADE','PRIMARY KEY(person_id,day)','job["session"] != session','last_fingerprint','incompatible_profiles')){Verify ($people.Contains($marker)) "Personenvertrag fehlt: $marker"}
$flow=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'nodered/rovo_neu_flows.json') | ConvertFrom-Json
$panel=$flow | Where-Object id -eq 'v420261020000003'
foreach($marker in @('people.enroll.request','people.enroll.confirm','consentChecked','people.fact.add','people.delete')){Verify ($panel.format.Contains($marker)) "Personenseite fehlt: $marker"}
$core=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'rovo/core.py')
$actions=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'rovo/application/actions.py')
Verify ($actions.Contains('core.people.suspend()')) 'Privatsphaere muss Registrierung abbrechen'
Verify ($actions.Contains('core.people.cancel()')) 'Stop muss Registrierung abbrechen'
$parser=Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'rovo/intents.py')
Verify (-not $parser.Contains('if text in')) 'Keine zweite feste Satzliste im Parser'
Verify (([regex]::Matches($parser,'catalog_match\(raw\)')).Count -eq 1) 'Ein Katalog-Lookup pro Eingabe'
Verify (-not $core.Contains('FAQ =') -and -not $core.Contains('FAQ.get')) 'Keine doppelte FAQ-Tabelle im Core'
Write-Output "KATALOG/PERSONEN: $checks statische Pruefungen bestanden; $phrases Formulierungen in $($catalog.intents.Count) Gruppen. Python-/Kameratests bleiben erforderlich."
