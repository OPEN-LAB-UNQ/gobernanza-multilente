const {test}=require('node:test'); const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const app=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
// El 13/10/2026 dos navegadores pidieron 248 veces un informe borrado: el detalle reintentaba sin fin.
function entorno(status){
 const timers=[];const toasts=[];
 const ctx=vm.createContext({state:{detalleId:323,areas:[1]},cargarAreas(){},toast:(m)=>toasts.push(m),
  setTimeout:(fn,ms)=>{timers.push(ms);return timers.length;},clearTimeout(){},
  apiFetch:async()=>{const e=new Error('x');e.status=status;throw e;},escapeDeep:(x)=>x});
 vm.runInContext(app.slice(app.indexOf('const MAX_REINTENTOS_DETALLE'),app.indexOf('  // Todo lo que puede citar texto literal del archivo')) + '\n}',ctx);
 return {ctx,timers,toasts};
}
for (const [status,texto] of [[404,'no existe'],[401,'sesión venció'],[403,'permiso']]) {
 test(`detalle con ${status} avisa y no reintenta`,async()=>{
  const {ctx,timers,toasts}=entorno(status);await ctx.refrescarDetalle();
  assert.equal(timers.length,0);assert.ok(toasts[0].includes(texto));
 });
}
test('error transitorio reintenta con espera creciente y se detiene',async()=>{
 const {ctx,timers,toasts}=entorno(500);
 for (let i=0;i<6;i++) await ctx.refrescarDetalle();
 assert.deepEqual(timers,[4500,9000,13500,18000,22500]);
 assert.ok(toasts.at(-1).includes('Probá recargar'));
});
