<template>
<div class="rx">
 <header class="rx-head"><div><div class="rx-kicker">PERSONEN / LOKALE PROFILE</div><h1>Personen & Gesichtsanmeldung</h1><div class="rx-sub">Einwilligung, geführte Ansichten und lokale Profilinformationen.</div></div></header>
 <div class="rx-grid">
  <section class="rx-panel rx-span-7"><h2>Gesicht anmelden</h2>
   <p class="rv-tip">Genau eine Person vor der Kamera. Rovo fordert Ansichten von vorn, links, rechts, oben und unten an. Dein eigener Kopf wird gedreht; der Roboter bleibt während der Aufnahme ruhig.</p>
   <div class="rx-field"><label>Anzeigename</label><input class="rx-input" v-model="newName" maxlength="60" @input="consentToken='';consentChecked=false"/></div>
   <label class="rv-switch"><span>Ausgewählte Gesichtsbilder zusätzlich lokal aufbewahren</span><input type="checkbox" v-model="storeImages" @change="consentToken='';consentChecked=false"/></label>
   <div class="rx-buttons"><button class="rx-button" @click="requestEnrollment">Einwilligung anfragen</button><button class="rx-button" @click="rpc('people.status')">Fortschritt lesen</button><button class="rx-button" @click="cancelEnrollment">Abbrechen</button></div>
   <div v-if="consentToken" class="rv-warning"><p>{{consentMessage}}</p><label><input type="checkbox" v-model="consentChecked"/> Ja, ich bin die Zielperson und erlaube die beschriebene lokale Speicherung.</label><button class="rx-button" :disabled="!consentChecked" @click="confirmEnrollment">Einwilligung bestätigen</button></div>
   <div class="rv-status" role="status">{{notice}}</div><div class="rv-tip" role="status">{{guidance}}</div>
   <p v-if="bridgeInfo?.people">Status: {{bridgeInfo.people.enrollment.state}} · {{bridgeInfo.people.enrollment.accepted||0}} / {{bridgeInfo.people.enrollment.target||0}} · Pose: {{bridgeInfo.people.enrollment.pose||'—'}}</p>
   <p v-if="!bridgeInfo?.people?.verified" class="rv-warning">Wiedererkennung ist noch nicht am Gerät validiert. Namensbegrüßungen bleiben bis zur ausdrücklichen Konfiguration gesperrt.</p>
  </section>
  <section class="rx-panel rx-span-5"><h2>Gespeicherte Profile</h2><button class="rx-button" @click="rpc('people.list')">Liste aktualisieren</button>
   <p v-if="!people.length">Keine geladenen Profile. Neue Profile entstehen ausschließlich über die Gesichtsanmeldung.</p>
   <div v-for="person in people" :key="person.id" class="rx-row"><div><strong>{{person.name}}</strong><div class="rx-small">{{person.sample_count}} Ansichten · {{person.image_count}} gespeicherte Bilder</div></div><div><button class="rx-button" @click="editPerson(person)">Bearbeiten</button><button class="rx-button" @click="askDelete(person)">Löschen</button></div></div>
  </section>
  <section v-if="selected.id" class="rx-panel rx-span-12"><h2>Profil bearbeiten</h2>
   <div class="rx-field"><label>Name</label><input class="rx-input" v-model="selected.name" maxlength="60"/></div>
   <div class="rx-field"><label>Informationen, bewusst mitgeteilt</label><input class="rx-input" v-model="selected.info" maxlength="500"/></div>
   <div class="rx-field"><label>Notizen</label><textarea class="rx-input" v-model="selected.notes" maxlength="1000"></textarea></div>
   <button class="rx-button" @click="saveProfile">Vorhandenes Profil speichern</button>
   <h3 style="margin-top:20px">Gesprächsthema ergänzen</h3>
   <div class="rx-field"><label>Kurzes Thema, beispielsweise Modellbau</label><input class="rx-input" v-model="factTopic" maxlength="60"/></div>
   <div class="rx-field"><label>Ausdrücklich mitgeteilte Information</label><input class="rx-input" v-model="factText" maxlength="500"/></div>
   <label class="rv-switch"><span>Rovo darf bei Begrüßungen gelegentlich nach diesem Thema fragen</span><input type="checkbox" v-model="factGreeting"/></label>
   <button class="rx-button" @click="saveFact">Profilinformation speichern</button>
   <p v-for="fact in facts" :key="fact.id"><strong>{{fact.topic}}:</strong> {{fact.text}} <span v-if="fact.greeting">· Begrüßung erlaubt</span></p>
   <p class="rv-tip">Profile und Merkmale bleiben lokal. Begrüßung einmal pro Berliner Kalendertag; freigegebene Themen höchstens einmal pro Woche. Keine automatische Ableitung privater Eigenschaften.</p>
  </section>
 </div>
</div>
</template>
<script>
export default {
 data(){return {people:[],notice:'',guidance:'',newName:'',storeImages:false,consentToken:'',consentMessage:'',consentChecked:false,selected:{id:'',name:'',info:'',notes:''},facts:[],factTopic:'',factText:'',factGreeting:false}},
 mounted(){this.rpc('people.list')},
 watch:{msg:{immediate:true,handler(m){const p=m?.payload;if(p?.kind==='snapshot'){const e=(p.events||[]).filter(e=>e.type?.startsWith('people.')).at(-1);if(e)this.guidance=e.text||e.details||'';return}if(p?.kind!=='rovo_people')return;this.notice=p.message||'';if(Array.isArray(p.people))this.people=p.people;if(Array.isArray(p.facts))this.facts=p.facts;if(p.ok&&p.enrollment?.confirmation_token){this.consentToken=p.enrollment.confirmation_token;this.consentMessage=p.enrollment.message;this.consentChecked=false}if(p.action==='people.enroll.confirm'||p.action==='people.enroll.cancel'){this.consentToken='';this.consentChecked=false}if(p.ok&&p.action==='people.delete'){this.selected={id:'',name:'',info:'',notes:''};this.facts=[]}}}},
 methods:{
  rpc(action,data={}){this.send({payload:{action,data}})},
  requestEnrollment(){if(!this.newName.trim())return;this.consentToken='';this.consentChecked=false;this.rpc('people.enroll.request',{name:this.newName.trim(),store_images:this.storeImages})},
  confirmEnrollment(){if(!this.consentChecked||!this.consentToken)return;this.rpc('people.enroll.confirm',{token:this.consentToken,consent:true})},
  cancelEnrollment(){this.consentToken='';this.consentChecked=false;this.rpc('people.enroll.cancel')},
  editPerson(person){this.selected={id:person.id,name:person.name,info:person.info||'',notes:person.notes||''};this.rpc('people.facts',{id:person.id})},
  saveProfile(){if(this.selected.id)this.rpc('people.save',{...this.selected})},
  askDelete(person){if(window.confirm('Profil von '+person.name+' einschließlich aktiver Gesichtsbilder, Merkmale und Profilinformationen löschen? Backups werden nicht automatisch gelöscht.'))this.rpc('people.delete',{id:person.id,confirm:true})},
  saveFact(){if(this.selected.id&&this.factTopic.trim()&&this.factText.trim())this.rpc('people.fact.add',{id:this.selected.id,topic:this.factTopic.trim(),text:this.factText.trim(),greeting:this.factGreeting})}
 }
}
</script>
