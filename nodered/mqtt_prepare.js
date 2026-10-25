const p=msg.payload;
if(!p||typeof p!=='object'||Array.isArray(p))return null;
const action=typeof p.action==='string'?p.action:p.type, client=msg._client;
const failure=message=>node.send([null,{_client:client,payload:{kind:action==='chat.send'?'chat_response':'ack',ok:false,ready:false,message,text:message}}]);
const allowed=new Set(['status','ui.sync','config.read','motion.home','motion.set','motion.stop','tracking.start','tracking.stop','camera.enable','camera.disable','display.emotion','chat.send','audio.test','audio.stop','privacy.enable','privacy.disable','people.list','people.save','people.delete','people.status','people.enroll.request','people.enroll.confirm','people.enroll.cancel','people.fact.add','people.facts']);
for(const action of ['audio.configure','motion.configure','camera.configure','motion.relative','motion.sequence','behavior.gaze','music.spotify','music.spotify.search','music.spotify.play_uri','music.spotify.queue','music.spotify.shuffle','music.pause','music.resume','music.stop','music.volume','alarm.add','alarm.list','alarm.change','alarm.snooze','timer.start','timer.status','timer.action','notes.list','notes.add','stopwatch.action','game.start','game.cancel'])allowed.add(action);
for(const supported of ['display.configure','settings.save','settings.restore','calibration.apply'])allowed.add(supported);
for(const supported of ['llm.save','llm.test','llm.forget','llm.models','spotify.save','spotify.login','spotify.complete','spotify.cancel','spotify.test','spotify.devices','spotify.select','spotify.disconnect'])allowed.add(supported);
if(!allowed.has(action)){failure('Diese V5-Aktion ist nicht eingerichtet.');return null;}
const data=p.data||{};
if(typeof data!=='object'||Array.isArray(data)||JSON.stringify(data).length>9000){failure('Ungültige Argumente.');return null;}
const boot=flow.get('rovoBoot'), live=flow.get('rovoLive')||0;
if(!boot||Date.now()-live>6500){failure('ROVO über MQTT nicht erreichbar.');return null;}
const pending=flow.get('rovoPending')||{};
if(Object.keys(pending).length>=128){failure('Zu viele offene Anfragen.');return null;}
const id=Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)+'_'+Math.random().toString(36).slice(2);
pending[id]={client,action,at:Date.now()}; flow.set('rovoPending',pending);
return [{topic:'rovo/v1/command',qos:'1',retain:false,payload:JSON.stringify({id,boot_id:boot,session:String(client?.socketId||'dashboard').replace(/[^A-Za-z0-9_-]/g,'_').slice(0,128),issued_at:Date.now()/1000,action,data})},null];
