const pending=flow.get('rovoPending')||{}, packets=[];
for(const [id,request] of Object.entries(pending)){
 if(Date.now()-request.at>30000){
  const message='MQTT-Antwort ausgeblieben. Zustand prüfen; Auftrag wird nicht automatisch wiederholt.';
  packets.push({_client:request.client,payload:{kind:request.action==='chat.send'?'chat_response':'ack',ok:false,message,text:message}});
  delete pending[id];
 }
}
flow.set('rovoPending',pending);
if((flow.get('rovoLive')||0)>0&&Date.now()-flow.get('rovoLive')>6500){
 flow.set('rovoLive',0);flow.set('rovoBoot',null);
 packets.push({payload:{kind:'snapshot',bridge:{online:false},tele:{},events:[]}});
}
return [packets];
