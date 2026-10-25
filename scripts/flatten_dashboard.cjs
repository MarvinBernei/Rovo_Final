// FlowFuse ui-template unterstützt genau einen Export und keine Vue-Mixins.
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const requireDashboard = createRequire(path.join(process.env.ROVO_NODE_RED_DIR || path.join(process.env.USERPROFILE || process.env.HOME, '.node-red'), 'package.json'));
const acorn = requireDashboard('acorn');
const generate = requireDashboard('escodegen').generate;
const file = process.argv[2];
const flow = JSON.parse(fs.readFileSync(file, 'utf8'));
const properties = object => Object.fromEntries(object.properties.map(p => [p.key.name || p.key.value, p.value]));
const expression = code => acorn.parse('('+code+')', {ecmaVersion:'latest'}).body[0].expression;
const optionKey = key => {
  if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key)) throw new Error('Nicht unterstützter FlowFuse-Optionsname: '+key);
  return key;
};
const chain = (first, second) => expression(`function(...args){(${generate(first)}).apply(this,args);(${generate(second)}).apply(this,args)}`);
for (const node of flow.filter(n => n.type === 'ui-template' && n.templateScope === 'local')) {
  node.format = node.format.replace(/<script>([\s\S]*?)<\/script>/, (whole, script) => {
    const tree = acorn.parse(script, {ecmaVersion:'latest',sourceType:'module'});
    const declaration = tree.body.find(n => n.type === 'ExportDefaultDeclaration');
    const mixin = tree.body.find(n => n.type === 'VariableDeclaration' && n.declarations[0].id.name === 'rovoBridge');
    if (!mixin) return whole;
    const base = properties(mixin.declarations[0].init), result = properties(declaration.declaration);
    delete result.mixins;
    result.data = expression(`function(){return Object.assign({},(${generate(base.data)}).call(this),(${generate(result.data)}).call(this))}`);
    for (const key of ['computed','methods']) {
      if (base[key]) result[key] = expression(`({${generate(base[key]).slice(1,-1)},${result[key] ? generate(result[key]).slice(1,-1) : ''}})`);
    }
    for (const key of ['mounted','unmounted']) {
      if (base[key]) result[key] = result[key] ? chain(base[key],result[key]) : base[key];
    }
    const watches = result.watch ? properties(result.watch) : {};
    for (const [key, value] of Object.entries(properties(base.watch))) {
      if (!watches[key]) {watches[key] = value;continue;}
      const baseWatch = properties(value);
      const original = watches[key].type === 'ObjectExpression' ? properties(watches[key]).handler : watches[key];
      watches[key] = expression(`({immediate:true,handler:${generate(chain(baseWatch.handler,original))}})`);
    }
    result.watch = expression('({'+Object.entries(watches).map(([key,value])=>optionKey(key)+':'+generate(value)).join(',')+'})');
    const code = 'export default {'+Object.entries(result).map(([key,value])=>optionKey(key)+':'+generate(value)).join(',\n')+'};';
    const checked = acorn.parse(code,{ecmaVersion:'latest',sourceType:'module'});
    if(checked.body.length!==1)throw new Error('Ungültige FlowFuse-Komponente '+node.id);
    return '<script>\n'+code+'\n</script>';
  });
}
fs.writeFileSync(file,JSON.stringify(flow,null,2)+'\n');
console.log('FlowFuse-kompatible Komponenten erzeugt.');
