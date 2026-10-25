// Verwendet dieselbe lokale Vue-Installation wie das Node-RED-Dashboard.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const dependencyRoot = process.argv[2] || path.join(process.env.USERPROFILE || process.env.HOME, '.node-red');
const requireVue = createRequire(path.join(dependencyRoot, 'package.json'));
const Vue = requireVue('vue');
const {parse} = requireVue('@vue/compiler-sfc');
const {compile} = requireVue('@vue/compiler-dom');
const acorn = requireVue('acorn');
const {renderToString} = requireVue('@vue/server-renderer');
const flow = JSON.parse(fs.readFileSync(path.join(__dirname, '../nodered/rovo_neu_flows.json'), 'utf8'));
const snapshot = process.argv.includes('--snapshot-stdin') ? JSON.parse(fs.readFileSync(0,'utf8')) : null;
const dashboardAssets = path.join(dependencyRoot, 'node_modules/@flowfuse/node-red-dashboard/dist/assets');
const bundle = fs.readdirSync(dashboardAssets).filter(name => /^index-.*\.js$/.test(name)).map(name => fs.readFileSync(path.join(dashboardAssets,name),'utf8')).find(text => text.includes('function parseSFC('));
if (!bundle) throw new Error('Installierter FlowFuse-Parser nicht gefunden.');
const parserCode = bundle.slice(bundle.indexOf('function processProperty('), bundle.indexOf('const VueParser='));
const parseFlowFuse = new Function('parse$2','escodegen',parserCode+';return parseSFC;')(acorn.parse,requireVue('escodegen'));
(async () => {
  let failed = 0;
  for (const widget of flow.filter(n => n.type === 'ui-template' && n.templateScope === 'local')) {
    try {
      const {descriptor, errors} = parse(widget.format);
      if (errors.length) throw new Error(errors.map(String).join('; '));
      const tree = acorn.parse(descriptor.script.content, {ecmaVersion:'latest',sourceType:'module'});
      if (tree.body.length !== 1 || tree.body[0].type !== 'ExportDefaultDeclaration') throw new Error('FlowFuse benötigt genau einen export default, ohne vorgelagerte Deklarationen.');
      const allowed = new Set(['name','data','computed','methods','watch','mounted','unmounted']);
      for (const property of tree.body[0].declaration.properties) {
        if (!allowed.has(property.key.name || property.key.value)) throw new Error('Nicht unterstützte FlowFuse-Option');
      }
      const {code} = compile(descriptor.template.content, {mode: 'function'});
      const component = parseFlowFuse(descriptor.script.content);
      if (typeof component.data !== 'function') throw new Error('FlowFuse übernimmt keine data-Funktion: Optionsschlüssel müssen unquotierte Bezeichner sein.');
      const vm = {send() {}};
      Object.assign(vm, component.data.call(vm));
      for (const [key,method] of Object.entries(component.methods || {})) vm[key] = method.bind(vm);
      const originalInterval = global.setInterval;
      global.setInterval = () => 0;
      try { component.mounted?.call(vm); component.unmounted?.call(vm); }
      finally { global.setInterval = originalInterval; }
      component.render = new Function('Vue', code)(Vue);
      const app = Vue.createSSRApp({...component, props:{msg:{default:null}}}, {msg: snapshot ? {payload:snapshot} : null});
      app.mixin({methods: {send() {}}});
      const warnings = [];
      app.config.warnHandler = message => warnings.push(message);
      const html = await renderToString(app);
      if (!html.includes('<h1>')) throw new Error('Kein Seiteninhalt gerendert.');
      if(snapshot && html.includes('Noch kein aktueller Core-Status empfangen.'))throw new Error('Laufzeit-Snapshot wurde nicht übernommen.');
      console.log('OK ' + widget.id);
    } catch (error) {
      failed++;
      console.error('FAIL ' + widget.id + ': ' + error.message);
    }
  }
  process.exitCode = failed ? 1 : 0;
})();
