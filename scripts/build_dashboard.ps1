# Erzeugt den angepassten V5-Flow reproduzierbar aus der unveränderten Originaldatei.

param([string]$Source = 'C:\Users\BNI\Downloads\ROVO_V5_NodeRED.json')

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot

$output = Join-Path $projectRoot 'nodered/rovo_neu_flows.json'

$sourceBackup = Join-Path $projectRoot 'nodered/ROVO_V5_original.json'

if (-not (Test-Path -LiteralPath $sourceBackup)) {

    Copy-Item -LiteralPath $Source -Destination $sourceBackup

} elseif ((Get-FileHash -LiteralPath $Source).Hash -ne (Get-FileHash -LiteralPath $sourceBackup).Hash) {

    throw 'Die V5-Referenz unterscheidet sich von der Sicherung. Zuerst separat prüfen.'

}

if (Test-Path -LiteralPath $output) {

    $previous = Get-Content -Raw -Encoding UTF8 -LiteralPath $output | ConvertFrom-Json

    if ($previous | Where-Object { $_.type -eq 'ui-base' -and $_.path -eq '/rovo-neu' }) {

        $previousBackup = Join-Path $projectRoot 'nodered/rovo_basis_vor_v5.json'

        if (-not (Test-Path -LiteralPath $previousBackup)) { Copy-Item -LiteralPath $output -Destination $previousBackup }

    }

}

$sourceNodes = Get-Content -Raw -Encoding UTF8 -LiteralPath $sourceBackup | ConvertFrom-Json

$uiTab = 'd02026bb00000101'

$bridgeTab = 'rovo-v5-core-bridge'

$nodes = [System.Collections.Generic.List[object]]::new()

$widgets = @()

$utf8 = [System.Text.UTF8Encoding]::new($false)

$mixin = @'

const rovoBridge = {

 data(){return {bridgeInfo:null,bridgeNow:Date.now(),bridgeClock:null,runtimeState:null,runtimeEdit:{},runtimeDirty:false,runtimeInitialized:false,runtimeSection:'',runtimeQuery:'',runtimeRestoreConfirmed:false,runtimeRestoreSource:'saved',runtimeLimitsConfirmed:false,runtimeFaces:['NEUTRAL','LISTENING','THINKING','TALKING','HAPPY','CURIOUS','SLEEPY','SURPRISED','ERROR','SAD','ANGRY','CONFUSED','LAUGHING','WINK','BLINK','LOVE']}},

 methods:{

  runtimeSend(action,data){this.send({payload:{action,data}})},

  runtimeApply(section){const e=this.runtimeEdit;if(section==='limits'){this.runtimeSend('calibration.apply',{pan:{...this.runtimeState.limits.pan,min:e.panMin,max:e.panMax},tilt:{...this.runtimeState.limits.tilt,min:e.tiltMin,max:e.tiltMax},confirm:this.runtimeLimitsConfirmed});this.runtimeLimitsConfirmed=false;return}const data=section==='motion'?{speed:e.speed,acceleration:e.acceleration}:section==='display'?{brightness:e.brightness,mode:e.displayMode,face:e.displayFace}:section==='audio'?{speech_volume:e.speech_volume,speech_rate:e.speech_rate,music_volume:e.music_volume}:{deadzone:e.deadzone,gain:e.gain};this.runtimeSend(section+'.configure',data)}

 },

 computed:{

  bridgeFresh(){return !!this.bridgeInfo?.online && (this.bridgeNow-Date.parse(this.bridgeInfo.updated_at_utc))/1000<8},

  bridgeLabel(){if(!this.bridgeFresh)return 'Core offline oder Status veraltet';return this.bridgeInfo.simulation?'SIMULATION · keine Nano-Hardwaremessung':('Core verbunden · Safe Mode '+(this.bridgeInfo.safe_mode?'aktiv':'aus'))}

 },

 mounted(){this.bridgeClock=setInterval(()=>this.bridgeNow=Date.now(),1000)},

 unmounted(){clearInterval(this.bridgeClock)},

 watch:{msg:{immediate:true,handler(m){const p=m?.payload;if(p?.kind==='snapshot'&&p.bridge){

  this.bridgeInfo=p.bridge;

  if(p.runtime){this.runtimeState=p.runtime;if(!this.runtimeDirty){const r=p.runtime;this.runtimeEdit={speed:r.motion.speed_limit_deg_s,acceleration:r.motion.acceleration_limit_deg_s2,speech_volume:r.audio.speech_volume_percent,speech_rate:r.audio.speech_rate,music_volume:r.audio.music_volume_percent,deadzone:r.camera.deadzone,gain:r.camera.gain,brightness:r.display.brightness,displayMode:r.display.mode,displayFace:r.display.face,panMin:r.limits.pan.min,panMax:r.limits.pan.max,tiltMin:r.limits.tilt.min,tiltMax:r.limits.tilt.max}}}

  if(this.cfg&&p.config){for(const section of Object.keys(p.config)){this.cfg[section]={...this.cfg[section],...p.config[section]}}}

  if(this.form&&p.config&&!this.runtimeInitialized){const section=Object.prototype.hasOwnProperty.call(this.form,'homePan')?'motion':Object.prototype.hasOwnProperty.call(this.form,'emotion')?'display':Object.prototype.hasOwnProperty.call(this.form,'autoTracking')?'camera':'audio';this.form={...this.form,...p.config[section]};this.runtimeInitialized=true}

  if(this.form&&Object.prototype.hasOwnProperty.call(this.form,'emotion')&&p.runtime)this.form.emotion=p.runtime.display.emotion;

  if(this.cfg){this.cfg.motion.enabled=p.bridge.motion_available===true;this.cfg.camera.enabled=p.bridge.camera_online===true;this.cfg.camera.autoTracking=p.bridge.tracking===true;this.cfg.audio.enabled=p.bridge.tts_configured===true;this.cfg.display.enabled=p.bridge.display_available===true}

  if(this.form&&Object.prototype.hasOwnProperty.call(this.form,'homePan'))this.form.enabled=p.bridge.motion_available===true;

  if(this.form&&Object.prototype.hasOwnProperty.call(this.form,'autoTracking')){this.form.enabled=p.bridge.camera_online===true;this.form.autoTracking=p.bridge.tracking===true}

 }else if(p?.kind==='ack'&&p.ok){this.runtimeDirty=false}} }}

};

export default {mixins:[rovoBridge],

'@

$banner = @'

<div class="rx">

<div class="rv-warning" role="status" :style="{borderColor:bridgeFresh?'#6d928e':'#d58b69'}">

<strong>{{bridgeLabel}}</strong>

<span v-if="bridgeFresh && !bridgeInfo.calibrated"> · Bewegung ohne Kalibrierung gesperrt</span>

<div class="rx-small">ROVO-Oberfläche am Core. Vorschauen sind keine gemessenen Positionen. Graue Verwaltungsfunktionen sind noch nicht eingerichtet.</div>

</div>

'@

foreach ($node in $sourceNodes) {

    if ($node.id -eq $uiTab -or $node.type -in @('ui-base','ui-theme','ui-page','ui-group','ui-template')) {

        if ($node.type -eq 'ui-base') {

            $node | Add-Member -NotePropertyName includeClientData -NotePropertyValue $true -Force

            $node | Add-Member -NotePropertyName acceptsClientConfig -NotePropertyValue @('ui-control','ui-notification','ui-template') -Force

            $node.name = 'ROVO · Control Center / Core'
            $node.path = '/rovo'

        }

        if ($node.type -eq 'ui-template' -and $node.templateScope -eq 'local') {

            if ($node.id -eq 'v420261020000003') {

                $node.format = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'nodered/people_panel.vue')

            }

            $widgets += $node.id

            $node.wires = @(,@('rovo-v5-ui-out'))

            $node | Add-Member -NotePropertyName passthru -NotePropertyValue $false -Force

            $node | Add-Member -NotePropertyName storeOutMessages -NotePropertyValue $false -Force

            $node | Add-Member -NotePropertyName resendOnRefresh -NotePropertyValue $false -Force

            $format = $node.format.Replace('export default {', $mixin)

            if (-not $format.Contains('mixins:[rovoBridge]')) { throw "Kein Vue-Export in $($node.id)" }

            $format = $format.Replace('<div class="rx">', $banner)

            $format = $format.Replace("this.notice='Testbefehl gesendet; keine Hardwarebewegung.'", "this.notice='Anfrage gesendet – Backendantwort abwarten.'")

            $format = $format.Replace("this.notice='Testbefehl gesendet.'", "this.notice='Anfrage gesendet – Backendantwort abwarten.'")

            $format = $format.Replace("this.notice='Testbefehl gesendet – Lautsprecherausgabe noch nicht verbunden.'", "this.notice='Anfrage gesendet – Backendantwort abwarten.'")

            $format = $format.Replace('Hardware: Testmodus','Core-Anbindung').Replace('Keine echte Servo-Ansteuerung','Backendfreigabe erforderlich')

            $format = $format.Replace('Die Hardware bleibt unverbunden','Ergebnis stammt vom Core')

            $format = $format.Replace('Position senden erzeugt momentan nur einen Testbefehl.', 'Position senden wird vom Core geprüft und nur innerhalb seiner Freigabe angenommen.')

            $format = $format.Replace('Bereits bekannte Ausgangswerte: Pan 75°, Tilt 90°.', 'Home-Werte stammen ausschließlich aus der bestätigten Core-Konfiguration.')

            $format = $format.Replace('70 % als Startwert. Die tatsächliche Wirkung setzt Unterstützung im Bewegungsprogramm voraus.', 'Web-Einstellung noch nicht unterstützt. Das geprüfte Firmwareprofil bleibt maßgeblich.')

            $format = $format.Replace('Empfehlung: 64 %. Die reale Lautstärke muss später an den Audio-Dienst übertragen werden.', 'Sprachlautstärke am geprüften ALSA-Mixer einstellen. Dieser Regler ist noch nicht angebunden.')

            $format = $format.Replace('Werden lokal gespeichert und nach einem Neustart geladen','Web-Speicherung noch nicht unterstützt; Core-Konfiguration schreibgeschützt.')

            $format = $format.Replace('Gespeicherte Werte','Core-Status · schreibgeschützt')

            $format = $format.Replace("this.notice='Befehl an Node-RED gesendet – Testmodus'", "this.notice='Anfrage gesendet – Backendantwort abwarten.'")

            $format = $format.Replace("'Im Testmodus verarbeitet'", "'Backendantwort empfangen'").Replace("model:'gpt-4o-mini'", "model:''")

            $format = $format.Replace('Die Auswahl wird dort gespeichert und vom Chat übernommen.', 'Die Anbieterverwaltung ist noch schreibgeschützt; maßgeblich ist die Core-Konfiguration.')

            $format = $format.Replace('Der Testmodus wartet auf Eingaben.', 'Das Ereignisprotokoll ist in dieser Anbindung noch nicht eingerichtet.')

            $format = $format.Replace('Die Position wird als Konfiguration gespeichert, nicht am Servo vermessen.', 'Web-Kalibrierung ist deaktiviert; Home und Grenzen stammen aus der geprüften Core-Konfiguration.')

            $format = $format.Replace('Personen werden hier zunächst manuell gespeichert; die automatische Gesichtserkennung ist noch nicht angebunden.', 'Personenverwaltung und Gesichtserkennung sind im neuen Core noch nicht eingerichtet.')

            $format = $format.Replace('Einträge werden lokal auf diesem Rechner gespeichert.', 'Speichern und Löschen sind hier noch deaktiviert.')

            $format = $format.Replace('Stream wird angezeigt, sobald das Python-Kameraprogramm angebunden ist','Livebild-Proxy noch nicht eingerichtet; Kamera-Schalter und Tracking verwenden den Core.')

            $format = $format.Replace('Kamera noch nicht verbunden','Status siehe Core-Anzeige')

            $format = $format.Replace('Die Einstellung wird gespeichert. Face Tracking funktioniert erst, wenn das Kameraprogramm sie auswertet.','Kamera und Tracking werden unmittelbar im Core angefordert. Empfindlichkeit bleibt schreibgeschützt.')

            $format = $format.Replace('{pan:this.pan,tilt:this.tilt,speed:this.form.speed}', '{pan:this.pan,tilt:this.tilt}')

            $format = $format.Replace("this.rpc('config.update',{section:'display',changes:{emotion:id}});", '')

            if ($node.id -eq 'd02026bb00003002') {

                $preview = '<div v-if="bridgeFresh &amp;&amp; bridgeInfo.camera_online &amp;&amp; !bridgeInfo.privacy"><img :src="''/rovo/camera.jpg?t=''+bridgeNow" alt="Aktuelles Kamerabild" style="max-width:100%;max-height:420px;object-fit:contain"/><p class="rx-small">HTTP-Einzelbildvorschau, etwa ein Bild pro Sekunde.</p></div>'

                $format = $format.Replace('<div class="rx">',('<div class="rx">'+$preview))

                $format = $format.Replace('v-model="form.enabled"/>','v-model="form.enabled" @change="this.send({payload:{type:form.enabled?''camera.enable'':''camera.disable'',data:{}}})"/>')

                $format = $format.Replace('v-model="form.autoTracking" :disabled="!form.enabled"/>','v-model="form.autoTracking" :disabled="!form.enabled" @change="this.send({payload:{type:form.autoTracking?''tracking.start'':''tracking.stop'',data:{}}})"/>')

            }

            # Anfangswerte nicht als echte Kalibrierung oder Audio-/Kamerastatus ausgeben.

            $format = $format.Replace('homePan:75,homeTilt:90,speed:65,smoothing:70,panMin:50,panMax:105,tiltMin:70,tiltMax:110','homePan:null,homeTilt:null,speed:null,smoothing:null,panMin:null,panMax:null,tiltMin:null,tiltMax:null')

            $format = $format.Replace('pan:75,tilt:90','pan:null,tilt:null')

            $format = $format.Replace('enabled:true','enabled:false')

            $format = $format.Replace('trackingSensitivity:65','trackingSensitivity:null').Replace('brightness:75','brightness:null')

            $format = $format.Replace('volume:64,autoSpeak:true','volume:null,autoSpeak:false')

            $format = $format.Replace("this.notice=p.ok?'Konfiguration geladen.':p.message", "this.notice=p.message||'Core-Konfiguration gelesen.'")

            $format = $format.Replace('<span>Uptime</span>','<span>ROVO-Prozesslaufzeit</span>')

            $format = $format.Replace("{{tele.esp32.connected===true?'Verbunden':'Nicht erkannt'}}", "{{tele.esp32.connected===true?'Verbunden':tele.esp32.connected===false?'Getrennt':'Nicht gemessen'}}")

            $format = $format.Replace("{{tele.camera.connected===true?'Verbunden':'Nicht erkannt'}}", "{{tele.camera.connected===true?'Verbunden':tele.camera.connected===false?'Aus':'Unbekannt'}}")

            # Nur die HTML-Controls sperren; die V5-Methoden liefern weiter klare Fehlantworten.

            $scriptStart = $format.IndexOf('<script>')

            $html, $javascript = $format.Substring(0,$scriptStart), $format.Substring($scriptStart)

            $blockedFields = @('trackingSensitivity','speed','smoothing','panMin','panMax','tiltMin','tiltMax','allowExtendedRange','brightness','mode','volume','autoSpeak','continuous')

            if ($node.id -in @('d02026bb00003003','d02026bb00003004','d02026bb00003006')) { $blockedFields += 'enabled' }

            foreach ($field in $blockedFields) {

                $pattern = '<(?:input|select)\b[^>]*v-model(?:\.number)?="form\.' + $field + '"[^>]*>'

                $html = [regex]::Replace($html, $pattern, {

                    param($match)

                    $tag = [regex]::Replace($match.Value, '\s+:disabled="[^"]*"','')

                    if ($tag -notmatch '\sdisabled(?:\s|/?>)') { $tag = [regex]::Replace($tag, '(\s*/?>)$', ' disabled$1') }

                    $tag

                })

            }

            $html = [regex]::Replace($html, '<button\b[^>]*@click="(?:save|reset|saveBehavior|calibrate|saveLimits|resetLimits|saveLLM|testLLM|forgetLLM|saveSpotify|loginSpotify|disconnectSpotify|addOwnModel|removeOwnModel\([^"]*\))"[^>]*>', {

                param($match) [regex]::Replace($match.Value, '(>)$', ' disabled title="Im neuen Core noch nicht eingerichtet"$1')

            })

            if ($node.id -eq 'v420261020000003') {

                $html = [regex]::Replace($html, '<button\b[^>]*@click="remove\(p\)"[^>]*>', {

                    param($match) [regex]::Replace($match.Value, '(>)$', ' disabled title="Personenverwaltung noch nicht eingerichtet"$1')

                })

            }

            $node.name = $node.name.Replace('V5','ROVO')
            $node.format = ($html + $javascript).Replace('V5','ROVO')

            if ($node.id -eq 'c8261020b3000012') {
                $node.name = '08 · Verbindungen (KI und Spotify)'
                $node.format = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'nodered/connections_panel.vue')).Replace('export default {', $mixin).Replace('<div class="rx">', $banner)
            }

            $sections = @{'d02026bb00003002'='camera';'d02026bb00003003'='motion';'d02026bb00003004'='display';'d02026bb00003005'='system';'d02026bb00003006'='audio'}

            if ($sections.ContainsKey($node.id)) {

                $controls = [IO.File]::ReadAllText((Join-Path $projectRoot 'nodered/runtime_controls.html'))

                $node.format = $node.format.Insert($node.format.LastIndexOf('</template>'),$controls)

                $node.format = $node.format.Replace("runtimeSection:''",("runtimeSection:'"+$sections[$node.id]+"'"))

            }

        }

        $nodes.Add($node)

    }

}

function Add-Node($node) { $nodes.Add([pscustomobject]$node) }

Add-Node @{id=$bridgeTab;type='tab';label='ROVO · Dashboard an Python-Core';disabled=$false;info='MQTT-Dashboard mit getrenntem HTTP-Kamerapfad. Kein alter Host-Exec und kein zweiter Gerätebesitzer.'}

Add-Node @{id='rovo-v5-ui-out';type='link out';z=$uiTab;name='Dashboard → gemeinsamer Core';mode='link';links=@('rovo-v5-in');x=1100;y=920;wires=@()}

Add-Node @{id='rovo-v5-in';type='link in';z=$bridgeTab;name='Dashboard-Befehle';links=@('rovo-v5-ui-out');x=80;y=140;wires=@(,@('rovo-v5-prepare'))}

Add-Node @{id='rovo-v5-ui-in';type='link in';z=$uiTab;name='Core → Oberfläche';links=@('rovo-v5-out');x=80;y=980;wires=@(,$widgets)}

Add-Node @{id='rovo-v5-out';type='link out';z=$bridgeTab;name='Nur bereinigte UI-Antworten';mode='link';links=@('rovo-v5-ui-in');x=1070;y=140;wires=@()}

$prepare = [IO.File]::ReadAllText((Join-Path $projectRoot 'nodered/mqtt_prepare.js'))

Add-Node @{id='rovo-v5-prepare';type='function';z=$bridgeTab;name='MQTT-Auftrag prüfen';func=$prepare;outputs=2;timeout=0;noerr=0;initialize='';finalize='';libs=@();x=440;y=140;wires=@(@('rovo-v5-mqtt-out'),@('rovo-v5-out'))}

Add-Node @{id='rovo-mqtt-broker';type='mqtt-broker';name='ROVO lokal – Zugangsdaten eintragen';broker='127.0.0.1';port='1883';clientid='rovo-nodered';autoConnect=$true;usetls=$false;protocolVersion='4';keepalive='15';cleansession=$true;autoUnsubscribe=$true}

Add-Node @{id='rovo-v5-mqtt-out';type='mqtt out';z=$bridgeTab;name='MQTT-Befehle, niemals retained';topic='';qos='1';retain='false';broker='rovo-mqtt-broker';x=700;y=140;wires=@()}

Add-Node @{id='rovo-v5-mqtt-in';type='mqtt in';z=$bridgeTab;name='MQTT Status und Antworten';topic='rovo/v1/+';qos='1';datatype='auto-detect';broker='rovo-mqtt-broker';nl=$false;rap=$true;rh=0;x=440;y=220;wires=@(,@('rovo-v5-result'))}

Add-Node @{id='rovo-camera-in';type='http in';z=$bridgeTab;name='Kameravorschau, Node-RED HTTP-Auth erforderlich';url='/rovo/camera.jpg';method='get';upload=$false;x=180;y=400;wires=@(,@('rovo-camera-prepare'))}

Add-Node @{id='rovo-camera-prepare';type='function';z=$bridgeTab;name='Kamera-Token nur serverseitig';func='const token=env.get("ROVO_API_TOKEN");if(typeof token!=="string"||token.length<32){msg.statusCode=503;msg.payload="Kamera nicht eingerichtet";return [null,msg]}msg.method="GET";msg.url="http://127.0.0.1:1891/api/v1/camera.jpg";msg.headers={Authorization:"Bearer "+token};return [msg,null];';outputs=2;x=450;y=400;wires=@(@('rovo-camera-fetch'),@('rovo-camera-response'))}

Add-Node @{id='rovo-camera-fetch';type='http request';z=$bridgeTab;name='Nur JPEG über HTTP';method='use';ret='bin';url='';requestTimeout='3000';senderr=$false;x=700;y=400;wires=@(,@('rovo-camera-sanitize'))}

Add-Node @{id='rovo-camera-sanitize';type='function';z=$bridgeTab;name='Keine Tokens oder Upstream-Header im Browser';func='msg.headers={"Content-Type":msg.statusCode===200?"image/jpeg":"text/plain","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"};if(msg.statusCode!==200)msg.payload="Kein aktuelles Kamerabild";return msg;';outputs=1;x=920;y=400;wires=@(,@('rovo-camera-response'))}

Add-Node @{id='rovo-camera-response';type='http response';z=$bridgeTab;name='Kameraantwort';statusCode='';headers=@{};x=1160;y=400;wires=@()}

Add-Node @{id='rovo-v5-poll';type='inject';z=$bridgeTab;name='Antwortfristen und Lebenszeichen';props=@(@{p='payload'});repeat='1';once=$true;onceDelay=1;payload='';payloadType='date';x=180;y=60;wires=@(,@('rovo-v5-timeout'))}

Add-Node @{id='rovo-v5-timeout';type='function';z=$bridgeTab;name='Keine automatische Wiederholung';func=[IO.File]::ReadAllText((Join-Path $projectRoot 'nodered/mqtt_timeout.js'));outputs=1;timeout=0;noerr=0;initialize='';finalize='';libs=@();x=500;y=60;wires=@(,@('rovo-v5-out'))}

$response = @'

let envelope=msg.payload;

if(typeof envelope==='string'){try{envelope=JSON.parse(envelope);}catch{return null;}}

if(!envelope||typeof envelope!=='object')return null;

if(msg.topic==='rovo/v1/availability'){

 if(envelope.online===true&&typeof envelope.boot_id==='string'){flow.set('rovoBoot',envelope.boot_id);}

 else {flow.set('rovoBoot',null);flow.set('rovoLive',1);}

 return null;

}

if(msg.topic==='rovo/v1/status'){

 if(envelope.boot_id!==flow.get('rovoBoot')||envelope.snapshot?.kind!=='snapshot')return null;

 flow.set('rovoLive',Date.now());return [[{payload:envelope.snapshot}]];

}

if(msg.topic!=='rovo/v1/reply'||envelope.boot_id!==flow.get('rovoBoot'))return null;

const pending=flow.get('rovoPending')||{}, request=pending[envelope.id];

if(!request)return null;

delete pending[envelope.id];flow.set('rovoPending',pending);

msg.payload=envelope.result;msg.rovoAction=request.action;msg._client=request.client;

const b=msg.payload, a=msg.rovoAction, client=msg._client;

const packets=[];

const add=payload=>packets.push({_client:client,payload});

if(!b||typeof b!=='object'||typeof b.ok!=='boolean'){

 add({kind:'ack',ok:false,message:'Core nicht erreichbar oder falscher Dienst auf Port 1891.'});

 add({kind:'integrations',action:'status',ok:false,ready:false,message:'Core nicht erreichbar.'});

 return [packets];

}

const message=typeof b.message==='string'?b.message:'Keine gültige Core-Antwort.';

if(b.snapshot?.kind==='snapshot')add(b.snapshot);

if(a==='chat.send')add({kind:'chat_response',text:typeof b.reply==='string'?b.reply:message,ok:b.ok,emotion:b.result?.data?.emotion||null});

else if(a.startsWith('people.'))add({kind:'rovo_people',action:a,ok:b.ok,message,people:b.people||null,facts:b.facts||null,enrollment:b.enrollment||null});

else if(a==='config.read')add({kind:'rovo_config',action:a,ok:b.ok,config:b.config||null,message});

else if(a.startsWith('llm.')||a.startsWith('spotify.'))add({kind:'integrations',action:a,ok:b.ok,ready:b.ready===true,message,status:b.status||null,data:b.connection_data||null});

else if(a==='status'&&!msg.rovoPoll)add({kind:'integrations',action:a,ok:b.ok,ready:b.ready===true,message,status:b.status||null});

else if(a==='status')return [packets];

else if(a!=='ui.sync')add({kind:'ack',action:a,ok:b.ok,status:b.result?.status||'error',data:b.result?.data||null,message:(b.result?.simulated?'SIMULATION · ':'')+message});

return [packets];

'@

Add-Node @{id='rovo-v5-result';type='function';z=$bridgeTab;name='Core-Ergebnis → Dashboard, ohne Header';func=$response;outputs=1;timeout=0;noerr=0;initialize='';finalize='';libs=@();x=920;y=140;wires=@(,@('rovo-v5-out'))}

$ids=@{}

foreach($node in $nodes){if($ids.ContainsKey($node.id)){throw "Doppelte ID $($node.id)"};$ids[$node.id]=$true}

foreach($node in $nodes){

 foreach($group in $node.wires){foreach($target in $group){if(-not $ids.ContainsKey($target)){throw "Fehlender Wire $target"}}}

 foreach($target in $node.links){if(-not $ids.ContainsKey($target)){throw "Fehlender Link $target"}}

 foreach($field in @('z','ui','page','group','theme')){if($node.$field -and -not $ids.ContainsKey($node.$field)){throw "Fehlende Referenz $($node.$field)"}}

}

$stagedOutput = $output + '.building'

[System.IO.File]::WriteAllText($stagedOutput, (ConvertTo-Json -InputObject $nodes.ToArray() -Depth 100), $utf8)

$nodeCommand = if ($env:ROVO_NODE_EXE) { $env:ROVO_NODE_EXE } else { 'node' }

& $nodeCommand (Join-Path $PSScriptRoot 'flatten_dashboard.cjs') $stagedOutput

if ($LASTEXITCODE -ne 0) { throw 'FlowFuse-Komponenten konnten nicht aufgebaut werden.' }

[System.IO.File]::WriteAllText($output, [System.IO.File]::ReadAllText($stagedOutput), $utf8)

[System.IO.File]::Delete($stagedOutput)

Write-Output "Dashboard-Flow erzeugt: $($nodes.Count) Knoten, $($widgets.Count) Seiten-Widgets. Original und früherer Basisflow gesichert."

