$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$script:checks=0
function Verify([bool]$valid,[string]$message){if(-not $valid){throw $message};$script:checks++}
$questions=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'rovo/quiz.json') | ConvertFrom-Json
Verify ($questions.Count -ge 20) 'Mindestens 20 Quizfragen erwartet'
$seen=@{}
foreach($q in $questions){
 Verify ($q.options.Count -eq 3) 'Drei Antwortmoeglichkeiten erforderlich'
 Verify ($q.answer -ge 0 -and $q.answer -lt 3) 'Ungueltiger Loesungsindex'
 Verify ([bool]$q.explanation -and [bool]$q.question) 'Frage/Erklaerung fehlt'
 Verify (-not $seen.ContainsKey($q.question)) 'Doppelte Frage'
 $seen[$q.question]=$true
}
$checksByFile=@{
 'rovo/llm.py'=@('def system_prompt','def decode_answer','class TextLLM','EMOTIONS','build_request','value.get("allow_cloud") is True')
 'rovo/persona_de.md'=@('Robotic Observation and Voice Operator','Tischroboter','keine Aktionen','emotion','Einwilligung')
 'rovo/voice.py'=@('def wait_wake','core.privacy','recognizer.Reset()','follow_until = time.monotonic() + 15','session="hands-free"')
 'rovo/motion.py'=@('self.sequence_task.cancel()','source == "social"','self.sequence_until','base_pan','self.interrupt_sequence()')
 'rovo/activities.py'=@('CREATE TABLE IF NOT EXISTS alarms','last_day','time.monotonic()','questions[:5]','random.randint(1, 100)')
 'rovo/telemetry.py'=@('power_status','voltage_now','1e-6','math.isfinite','battery_percent')
 'rovo/core.py'=@('self.activities.due()','self.expressions.tick()','self.motion.social_until')
 'rovo/application/dialogue.py'=@('core.llm.respond')
 'rovo/application/actions.py'=@('Automatische mechanische Kalibrierung gesperrt')
 'rovo/esp.py'=@('asyncio.shield(task)','await self._io(self.serial.readline)')
}
foreach($file in $checksByFile.Keys){
 $content=Get-Content -Raw -Encoding UTF8 (Join-Path $root $file)
 foreach($marker in $checksByFile[$file]){Verify (([regex]::Replace($content,'\s','')).Contains([regex]::Replace($marker,'\s',''))) "Fehlt in ${file}: $marker"}
}
$config=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'config/default.json') | ConvertFrom-Json
Verify ($config.behavior.social_gaze -eq $false) 'Unbeaufsichtigte Blickbewegung standardmaessig aus'
Verify ($null -eq $config.power.supply) 'Keine UPS erfinden'
$package=Get-Content -Raw -Encoding UTF8 (Join-Path $root 'pyproject.toml')
Verify ($package.Contains('"persona_de.md", "quiz.json"')) 'Paketdaten fehlen'
Write-Output "DIALOG: $script:checks statische Daten-/Vertragspruefungen bestanden. Python-/Audio-/Hardwaretests bleiben offen."
