const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const fuente=fs.readFileSync(path.join(__dirname,'../static/contrato-simple.js'),'utf8');
function entorno(){
 const els={
  'contrato-campos':{value:'',handlers:{}},
  'contrato-moneda':{checked:false,handlers:{}},
  'contexto-validacion':{value:''},
  'contrato-aviso':{textContent:''},
 };
 for(const el of Object.values(els)) el.addEventListener=(evento,fn)=>{(el.handlers||={})[evento]=fn;};
 const ctx=vm.createContext({document:{getElementById:id=>els[id]||null},JSON,String,Object});
 vm.runInContext(fuente,ctx);
 return {els,declarar:()=>els['contrato-campos'].handlers.input()};
}
test('las casillas escriben el contrato que antes había que tipear',()=>{
 const e=entorno();
 e.els['contrato-campos'].value=' total , moneda ';
 e.declarar();
 assert.deepEqual(JSON.parse(e.els['contexto-validacion'].value),{campos_requeridos:['total','moneda']});
 e.els['contrato-moneda'].checked=true;
 e.els['contrato-moneda'].handlers.change();
 assert.deepEqual(JSON.parse(e.els['contexto-validacion'].value),{campos_requeridos:['total','moneda'],condiciones_criticas:['moneda']});
 assert.match(e.els['contrato-aviso'].textContent,/lo que se declara/);
});
test('sin condiciones no se declara nada',()=>{
 const e=entorno();
 e.els['contrato-campos'].value='   ,  ';
 e.declarar();
 assert.equal(e.els['contexto-validacion'].value,'');
 assert.equal(e.els['contrato-aviso'].textContent,'');
});
test('no pisa la declaracion escrita a mano y lo avisa',()=>{
 const e=entorno();
 e.els['contexto-validacion'].value='{"campos_requeridos":["importe_total"],"otra":1}';
 e.els['contrato-campos'].value='total';
 e.declarar();
 assert.equal(e.els['contexto-validacion'].value,'{"campos_requeridos":["importe_total"],"otra":1}');
 assert.match(e.els['contrato-aviso'].textContent,/editada a mano/);
});
