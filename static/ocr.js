'use strict';
/* Revisión de lectura: el original al lado de la tabla leída, editable. Nada se analiza hasta que
   la persona confirma la tabla. Las reglas de celdas dudosas replican services/ocr_local.py. */
const PERIODO_RE=/^(?:(?:19|20)\d{2}(?:[-/](?:0?[1-9]|1[0-2]))?|(?:0?[1-9]|1[0-2])[-/](?:19|20)\d{2}|(?:19|20)\d{2}\s*\*+)$/;
const ROTULOS_PERIODO=new Set(['ano','anio','anos','periodo','mes','fecha','year','trimestre','semestre','ejercicio']);
const AMBIGUO_RE=/^[-+(]?\d{1,3}[.,]\d{3}\)?%?$/;
const NUMERO_SUELTO=/^-?\(?(?:\d[\d.]*(?:,\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)\)?%?$/;
function sinAcentos(t){return String(t??'').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g,'').trim();}
function limpio(c){return String(c??'').split(/\s+/).filter(Boolean).join(' ');}
function tokenNumerico(texto){let t=String(texto??'').trim().replace(/[  $]/g,'');if(t.endsWith('%'))t=t.slice(0,-1);const neg=t.startsWith('(')&&t.endsWith(')');if(neg)t=t.slice(1,-1);return [t,neg];}
function numeroTabla(texto,formato){
 let [t,neg]=tokenNumerico(texto);
 if(!t||!/^[-+]?[\d.,]+$/.test(t)||!/\d/.test(t))return null;
 if(formato==='en'){if(!/^(?:[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)$/.test(t))return null;t=t.replace(/,/g,'');}
 else{if(!/^(?:[-+]?\d{1,3}(?:\.\d{3})*(?:,\d+)?|[-+]?\d+(?:,\d+)?)$/.test(t))return null;t=t.replace(/\./g,'').replace(',','.');}
 if(!/^[-+]?\d+(?:\.\d+)?$/.test(t))return null;
 if(neg&&!t.startsWith('-'))t='-'+t.replace(/^\+/,'');
 return t;
}
function detectarFormato(filas){
 let es=0,en=0;
 for(const f of filas)for(const c of f){const [t]=tokenNumerico(c);
  if(/^(?:-?\d+,\d{1,2}|-?\d{1,3}(?:\.\d{3})+,\d+|-?\d{1,3}(?:\.\d{3}){2,}|-?\d+,\d{4,})$/.test(t))es++;
  else if(/^(?:-?\d+\.\d{1,2}|-?\d{1,3}(?:,\d{3})+\.\d+|-?\d{1,3}(?:,\d{3}){2,}|-?\d+\.\d{4,})$/.test(t))en++;}
 return es>en?'es':en>es?'en':'ambiguo';
}
function anchoTabla(encabezado,filas){return Math.max(encabezado.length,...filas.map(f=>f.length),0);}
function columnasPeriodo(encabezado,filas){
 const out=[];
 for(let j=0;j<anchoTabla(encabezado,filas);j++){
  const valores=filas.map(f=>limpio(f[j])).filter(Boolean);
  if(ROTULOS_PERIODO.has(sinAcentos(encabezado[j]))||(valores.length>=2&&valores.filter(v=>PERIODO_RE.test(v)).length>=0.8*valores.length))out.push(j);
 }
 return out;
}
const esTotal=t=>sinAcentos(t).startsWith('total');
const decimales=t=>t.includes('.')?t.split('.')[1].length:0;
function variosNumeros(t){return String(t??'').split(/\s+/).filter(x=>NUMERO_SUELTO.test(x)).length>=2;}
function fmtEs(valor,partes){const dec=Math.max(0,...partes.map(decimales));return Number(valor).toLocaleString('es-AR',{minimumFractionDigits:dec,maximumFractionDigits:dec});}
function sumaSinSubtotales(columna,tol){
 const v=columna.map(x=>x==null?null:Number(x));const excl=new Set();
 let cambio=true;
 while(cambio){cambio=false;
  for(let k=0;k<v.length;k++){if(v[k]==null||excl.has(k))continue;let acc=0;const partes=[],usadas=[];
   for(let m=k+1;m<v.length;m++){if(excl.has(m))continue;if(v[m]==null)break;acc+=v[m];partes.push(columna[m]);usadas.push(m);
    if(partes.length>=2&&Math.abs(acc-v[k])<=tol(partes,columna[k])){usadas.forEach(x=>excl.add(x));cambio=true;break;}}}}
 if(!excl.size)return null;
 return v.reduce((s,x,k)=>x!=null&&!excl.has(k)?s+x:s,0);
}
// Jerarquía por código («1», «1.2», «1.2.1.», «A.1»): igual que codigo_fila de services/ocr_local.py.
const CODIGO_FILA=/^((?:\d{1,3}|[A-Z]|[IVX]{1,5})(?:\.\d{1,3})*)(\.?)(\s+\S.*)?$/;
const DESGLOSE=/\b(?:de (?:las|los) cuales|del cual|de la cual|incluye|entre (?:ellos|ellas))\b/;
function codigoFila(rotulo){const m=CODIGO_FILA.exec(rotulo||'');if(!m)return null;const k=m[1];
 if(m[3]&&!k.includes('.')&&!/^\d+$/.test(k)&&!m[2])return null;return k;}
function padresPorCodigo(codigos){
 const filaDe=new Map();for(const [i,k] of codigos)filaDe.set(k,i);const out=new Map();
 for(const [k,i] of filaDe){
  const hijos=[...filaDe.keys()].filter(x=>x.startsWith(k+'.')&&!x.slice(k.length+1).includes('.')).sort((a,b)=>filaDe.get(a)-filaDe.get(b));
  if(hijos.length<2||hijos.some(h=>filaDe.get(h)<i))continue;
  const ult=hijos.map(h=>h.split('.').pop());
  if(ult.every(u=>/^\d+$/.test(u))){const nums=ult.map(Number).sort((a,b)=>a-b);if(nums[0]>1||nums.some((n,x)=>n!==nums[0]+x))continue;}
  out.set(i,hijos.map(h=>filaDe.get(h)));
 }
 return out;
}
function codigosJerarquia(rotulos){
 const codigos=new Map();rotulos.forEach((r,i)=>{const k=codigoFila(r);if(k)codigos.set(i,k);});
 const vals=[...codigos.values()];
 if(codigos.size<3||!vals.some(k=>k.includes('.'))||new Set(vals).size!==vals.length||!padresPorCodigo(codigos).size)return new Map();
 return codigos;
}
function primerNivel(codigos,bloque){
 if(!codigos.size||bloque.some(k=>!codigos.has(k)))return [];
 const vals=bloque.map(k=>codigos.get(k));
 return bloque.filter(k=>{const v=codigos.get(k);return !vals.some(p=>p!==v&&v.startsWith(p+'.'));});
}
function celdasDudosas(encabezado,filas,formato){
 formato=formato||detectarFormato(filas);
 const dudosas=[],vistas=new Set();
 const marcar=(i,j,motivo)=>{const k=i+':'+j;if(!vistas.has(k)){vistas.add(k);dudosas.push({fila:i,columna:j,motivo});}};
 const ancho=anchoTabla(encabezado,filas);
 const rotulos=Array.from({length:ancho},(_,j)=>limpio(encabezado[j]));
 rotulos.forEach((r,j)=>{if(!r)marcar(-1,j,'Columna sin rótulo: escribí qué contiene.');else if(rotulos.filter(x=>x===r).length>1)marcar(-1,j,'Rótulo repetido: aclaralo para distinguir esta columna.');});
 const periodos=new Set(columnasPeriodo(rotulos,filas));
 for(const j of [...periodos].sort((a,b)=>a-b)){
  if(!filas.some(f=>limpio(f[j])))continue;
  filas.forEach((f,i)=>{if(!limpio(f[j]))marcar(i,j,'Período vacío: probablemente una celda combinada. Usá «Completar hacia abajo» en esta columna.');});
 }
 filas.forEach((f,i)=>f.forEach((c,j)=>{const t=limpio(c);if(!t||periodos.has(j))return;
  if(variosNumeros(t))marcar(i,j,'Hay más de un número en la celda: separalos en sus columnas.');
  else if(formato==='ambiguo'&&AMBIGUO_RE.test(t.replace(/ /g,'')))marcar(i,j,`Formato numérico ambiguo («${t}»): elegí el formato de la tabla (1.234,56 o 1,234.56).`);}));
 const fmt=formato==='en'?'en':'es';
 const valores=filas.map(f=>f.map(c=>numeroTabla(c,fmt)));
 const sumables=[];
 for(let j=0;j<ancho;j++){if(periodos.has(j)||rotulos[j].includes('%')||sinAcentos(rotulos[j]).includes('porc')||esTotal(rotulos[j]))continue;if(valores.filter(v=>v[j]!=null).length>=2)sumables.push(j);}
 const tol=(partes,total)=>{const unidad=10**-Math.max(0,...partes.concat([total]).map(decimales));return Math.max(0.5*unidad*(partes.length+1),Math.abs(Number(total))*0.001);};
 const rotulosFila=filas.map(f=>{const rot=f.map((c,j)=>[c,j]).find(([c,j])=>!periodos.has(j)&&limpio(c)&&numeroTabla(c,'es')==null&&numeroTabla(c,'en')==null);return rot?limpio(rot[0]):'';});
 const codigos=codigosJerarquia(rotulosFila);
 // Jerarquía por código: cada código padre es la suma de sus hijos inmediatos.
 // De abajo hacia arriba: si una subcuenta no cierra, el padre se compara con lo que suman las suyas.
 // Sin desgloses parciales («de las cuales») y sólo en columnas donde algún padre cierra.
 const padres=new Map([...padresPorCodigo(codigos)].filter(([i,hs])=>!hs.some(k=>DESGLOSE.test(sinAcentos(rotulosFila[k]))))),rec=new Map();
 const cierra=(i,j)=>{const total=valores[i][j];const partes=padres.get(i).map(k=>valores[k][j]??null);
  return total!=null&&partes.every(p=>p!=null)&&Math.abs(partes.reduce((s,x)=>s+Number(x),0)-Number(total))<=tol(partes,total);};
 const sumablesCodigo=sumables.filter(j=>[...padres.keys()].some(i=>cierra(i,j)));
 const prof=i=>codigos.get(i).split('.').length-1;
 for(const i of [...padres.keys()].sort((a,b)=>prof(b)-prof(a)||a-b)){
  const hijos=padres.get(i);const comp=[];
  for(const j of sumablesCodigo){const total=valores[i][j];const partes=hijos.map(k=>valores[k][j]??null);if(total==null||partes.some(p=>p==null))continue;
   const suma=partes.reduce((s,x)=>s+Number(x),0);const ok=Math.abs(suma-Number(total))<=tol(partes,total);
   const alt=hijos.reduce((s,k,x)=>s+(rec.has(k+':'+j)?rec.get(k+':'+j):Number(partes[x])),0);
   const expl=!ok&&hijos.some(k=>rec.has(k+':'+j))&&Math.abs(alt-Number(total))<=tol(partes,total);
   if(!ok&&!expl)rec.set(i+':'+j,alt);
   comp.push([j,suma,partes,ok||expl]);}
  if(comp.length>1&&!comp.some(c=>c[3]))continue;
  for(const [j,suma,partes,ok] of comp)if(!ok){const nombres=hijos.slice(0,4).map(k=>codigos.get(k)).join(', ')+(hijos.length>4?'…':'');
   marcar(i,j,`No suma: sus subcuentas (${nombres}) dan ${fmtEs(suma,partes)} y la fila dice ${limpio(filas[i][j])}.`);}
 }
 let inicio=0;
 filas.forEach((f,i)=>{
  if(!esTotal(rotulosFila[i]))return;
  const bloque=[];for(let k=inicio;k<i;k++)if(!filas[k].some((c,j)=>!periodos.has(j)&&esTotal(limpio(c))))bloque.push(k);
  inicio=i+1;if(bloque.length<2)return;
  const superior=primerNivel(codigos,bloque);
  for(const j of sumables){const total=valores[i][j];const partes=bloque.map(k=>valores[k][j]).filter(x=>x!=null);if(total==null||partes.length<2)continue;
   const suma=partes.reduce((s,x)=>s+Number(x),0);
   if(Math.abs(suma-Number(total))>tol(partes,total)){const aj=sumaSinSubtotales(bloque.map(k=>valores[k][j]??null),tol);if(aj!=null&&Math.abs(aj-Number(total))<=tol(partes,total))continue;
    const sup=superior.map(k=>valores[k][j]??null);
    if(sup.length>=2&&sup.every(v=>v!=null)&&Math.abs(sup.reduce((s,x)=>s+Number(x),0)-Number(total))<=tol(sup,total))continue;
    marcar(i,j,`No suma: las filas de arriba dan ${fmtEs(suma,partes)} y el total dice ${limpio(filas[i][j])}.`);}}
 });
 for(let jt=0;jt<ancho;jt++){if(!esTotal(rotulos[jt])||periodos.has(jt))continue;const pj=sumables.filter(j=>j<jt);if(pj.length<2)continue;
  valores.forEach((v,i)=>{const total=v[jt];const partes=pj.map(j=>v[j]).filter(x=>x!=null);if(total==null||partes.length<2)return;const suma=partes.reduce((s,x)=>s+Number(x),0);
   if(Math.abs(suma-Number(total))>tol(partes,total))marcar(i,jt,`No suma: las columnas de la fila dan ${fmtEs(suma,partes)} y el total dice ${limpio(filas[i][jt])}.`);});}
 return dudosas;
}
function completarHaciaAbajo(filas,columna){
 filas=filas.map(f=>f.slice());
 const llenas=filas.map((f,i)=>limpio(f[columna])?i:-1).filter(i=>i>=0);
 if(!llenas.length)return filas;
 const pasos=llenas.slice(1).map((b,k)=>b-llenas[k]);
 const cuenta={};pasos.forEach(p=>{cuenta[p]=(cuenta[p]||0)+1;});
 const paso=pasos.length?Number(Object.keys(cuenta).sort((a,b)=>cuenta[b]-cuenta[a])[0]):null;
 const desfase=llenas[0];
 const regular=Boolean(paso)&&desfase<paso&&pasos.every(p=>p===paso);
 const set=new Set(llenas);
 filas.forEach((f,i)=>{while(f.length<=columna)f.push('');if(limpio(f[columna]))return;
  if(regular){const origen=Math.floor(i/paso)*paso+desfase;if(origen<filas.length&&set.has(origen)){f[columna]=filas[origen][columna];return;}}
  const ant=llenas.filter(k=>k<i);if(ant.length)f[columna]=filas[ant[ant.length-1]][columna];});
 return filas;
}
function nombresUnicos(encabezado){
 const nombres=[];
 encabezado.forEach((r,j)=>{let n=limpio(r)||`columna_${j+1}`;
  if(nombres.includes(n)){const previo=nombres[nombres.length-1]||'';let c=previo?`${previo} · ${n}`:n;let k=2;while(nombres.includes(c)){c=`${n} (${k})`;k++;}n=c;}
  nombres.push(n);});
 return nombres;
}
function csvRevisado(encabezado,filas,formato){
 const fmt=formato==='en'?'en':'es';const ancho=anchoTabla(encabezado,filas);
 const texto=t=>{if(/^[=+@-]/.test(t))t="'"+t;return /[;"\n\r]/.test(t)?'"'+t.replace(/"/g,'""')+'"':t;};
 const celda=v=>{const t=limpio(v);const n=numeroTabla(t,fmt);return n!=null?n.replace(/^\+/,'').replace('.',','):texto(t);};
 const enc=encabezado.concat(Array(ancho-encabezado.length).fill(''));
 const lineas=[nombresUnicos(enc).map(texto).join(';')];
 for(const f0 of filas){const f=f0.concat(Array(ancho-f0.length).fill(''));if(!f.some(c=>limpio(c)))continue;lineas.push(f.map(celda).join(';'));}
 return '﻿'+lineas.join('\r\n')+'\r\n';
}
function nombreRevisado(nombre){const base=String(nombre||'documento').replace(/^.*[\\/]/,'').replace(/\.[^.]+$/,'')||'documento';return `${base} (revisado).csv`;}
function tablaDesdeTexto(texto){
 const filas=String(texto||'').split(/\r?\n/).map(l=>l.trim()).filter(Boolean).map(l=>l.split(/\t|\s{2,}/).map(c=>c.trim()));
 const ancho=Math.max(2,...filas.map(f=>f.length));const norm=filas.map(f=>f.concat(Array(ancho-f.length).fill('')));
 return {encabezado:norm[0]||Array(ancho).fill(''),filas:norm.slice(1)};
}
/* Compatibilidad: lectura de una tabla escrita a mano con tabulaciones. */
function tablaOCR(text){
 const rows=text.split(/\r?\n/).filter(x=>x.trim()).map(x=>x.split('\t').map(c=>c.trim()));
 if(rows.length<2||rows[0].length<2)throw new Error('La tabla necesita al menos dos columnas, encabezados y una fila de datos. Separá las columnas con tabulaciones.');
 if(rows.some(r=>r.length!==rows[0].length))throw new Error('Las filas no tienen la misma cantidad de columnas. Corregí la separación antes de exportar.');
 if(rows[0].some(x=>!x)||new Set(rows[0]).size!==rows[0].length)throw new Error('Usá encabezados completos y distintos.');
 return rows;
}
function csvOCR(rows){return '﻿'+rows.map(r=>r.map(c=>{let value=c;if(/^[=+@-]/.test(value)&&!/^[-+]?\d[\d.,]*$/.test(value))value="'"+value;return '"'+value.replace(/"/g,'""')+'"';}).join(';')).join('\r\n');}
/* Archivo traído desde la carga de Multilente (IndexedDB del mismo sitio). */
const REVISION_DB='gobernanza-revision-lectura';
function abrirDbRevision(){return new Promise((ok,mal)=>{const r=indexedDB.open(REVISION_DB,1);r.onupgradeneeded=()=>r.result.createObjectStore('archivos');r.onsuccess=()=>ok(r.result);r.onerror=()=>mal(r.error);});}
async function tomarArchivoPendiente(){const db=await abrirDbRevision();return new Promise((ok,mal)=>{const tx=db.transaction('archivos','readwrite');const st=tx.objectStore('archivos');const g=st.get('pendiente');g.onsuccess=()=>{st.delete('pendiente');ok(g.result||null);};g.onerror=()=>mal(g.error);});}
if(typeof module!=='undefined')module.exports={tablaOCR,csvOCR,numeroTabla,detectarFormato,columnasPeriodo,celdasDudosas,codigosJerarquia,completarHaciaAbajo,csvRevisado,nombresUnicos,nombreRevisado,tablaDesdeTexto};
if(typeof document!=='undefined'){
 const $=id=>document.getElementById(id);
 let result=null,file=null,current=0,tablaActual=0,bitmap=null,timer=null;
 const tablas={},confirmadas={};
 const clave=()=>`${current}:${tablaActual}`;
 function download(name,body,type){const url=URL.createObjectURL(new Blob([body],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function estadoLegible(p){return ({para_revisar:'para revisar',sin_texto:'sin texto reconocible',no_leida:'no se pudo leer'})[p.estado]||'revisar';}
 function tabla(){const p=result.paginas[current];const k=clave();if(!tablas[k]){const t=(p.tablas||[])[tablaActual];if(!t)return null;tablas[k]={encabezado:t.encabezado.slice(),filas:t.filas.map(f=>f.slice()),formato:t.formato_numerico==='en'?'en':'es',titulo:t.titulo||'',notas:t.notas||[],cifras:t.cifras_pagina||null,origen:t.origen||''};}return tablas[k];}
 function desconfirmar(){confirmadas[clave()]=false;$('confirmed').checked=false;botones();}
 function botones(){const t=tabla();const ok=Boolean(t&&confirmadas[clave()]);$('analizar').disabled=!ok;$('csv').disabled=!ok;}
 function paint(){if(!bitmap)return;const c=$('image');c.width=bitmap.width;c.height=bitmap.height;const ctx=c.getContext('2d');ctx.drawImage(bitmap,0,0);ctx.strokeStyle='#bb6500';ctx.lineWidth=3;for(const l of result.paginas[current].lineas||[])for(const w of l.palabras||[])if(w.confianza<80)ctx.strokeRect(...w.caja);}
 function marcarDudas(){const t=tabla();if(!t)return;const d=celdasDudosas(t.encabezado,t.filas,t.formato);const porCelda=new Map(d.map(x=>[x.fila+':'+x.columna,x.motivo]));
  $('grid').querySelectorAll('[data-i]').forEach(el=>{const m=porCelda.get(el.dataset.i+':'+el.dataset.j);el.classList.toggle('dudosa',Boolean(m));el.title=m||'';});
  $('dudas').textContent=d.length?`${d.length} ${d.length===1?'celda para revisar':'celdas para revisar'} (resaltadas).`:'Sin celdas marcadas. Igual compará la tabla con el original.';}
 function renderTabla(){
  const t=tabla();$('sin-tabla').hidden=Boolean(t);$('editor').hidden=!t;$('titulo-tabla').textContent=t?[t.titulo,...t.notas].filter(Boolean).join(' · '):'';
  botones();if(!t){$('grid').replaceChildren();return;}
  $('formato').value=t.formato;
  const ancho=anchoTabla(t.encabezado,t.filas);while(t.encabezado.length<ancho)t.encabezado.push('');t.filas.forEach(f=>{while(f.length<ancho)f.push('');});
  const tb=document.createElement('table');const thead=document.createElement('thead');const hr=document.createElement('tr');hr.append(document.createElement('th'));
  t.encabezado.forEach((h,j)=>{const th=document.createElement('th');th.contentEditable='true';th.dataset.i='-1';th.dataset.j=j;th.textContent=h;hr.append(th);});thead.append(hr);tb.append(thead);
  const body=document.createElement('tbody');
  t.filas.forEach((f,i)=>{const tr=document.createElement('tr');const n=document.createElement('td');n.className='num';n.textContent=i+1+' ';const del=document.createElement('button');del.type='button';del.textContent='×';del.title='Quitar esta fila';del.setAttribute('aria-label',`Quitar fila ${i+1}`);del.onclick=()=>{t.filas.splice(i,1);desconfirmar();renderTabla();};n.append(del);tr.append(n);
   f.forEach((c,j)=>{const td=document.createElement('td');td.contentEditable='true';td.dataset.i=i;td.dataset.j=j;td.textContent=c;tr.append(td);});body.append(tr);});
  tb.append(body);$('grid').replaceChildren(tb);
  const sel=$('col-completar');sel.replaceChildren();const per=columnasPeriodo(t.encabezado,t.filas);
  t.encabezado.forEach((h,j)=>{const o=document.createElement('option');o.value=j;o.textContent=h||`Columna ${j+1}`;sel.append(o);});if(per.length)sel.value=per[0];
  const unir=$('unir');unir.replaceChildren();
  result.paginas.forEach((p,pi)=>(p.tablas||[]).forEach((x,ti)=>{if(pi===current&&ti===tablaActual)return;const k=`${pi}:${ti}`;const enc=(tablas[k]||x).encabezado;if(enc.length!==ancho)return;const o=document.createElement('option');o.value=k;o.textContent=`Página ${p.pagina}, tabla ${ti+1}${x.titulo?' · '+x.titulo.slice(0,50):''}`;unir.append(o);}));
  $('unir-box').hidden=!unir.options.length;
  marcarDudas();
 }
 function show(){
  const p=result.paginas[current];
  const metodo=p.metodo==='texto_pdf'?'<span class="badge texto">Texto del PDF</span>':p.metodo==='ocr_local'?'<span class="badge ocr">OCR: revisá números y signos</span>':'';
  $('method').innerHTML=metodo;if(p.error){const s=document.createElement('span');s.textContent=' '+p.error;$('method').append(s);}
  if(p.aviso_cifras){const s=document.createElement('strong');s.textContent=' '+p.aviso_cifras;$('method').append(s);}
  const sel=$('tablas');sel.replaceChildren();(p.tablas||[]).forEach((t,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`Tabla ${i+1}${t.titulo?' · '+t.titulo.slice(0,60):''} (${t.filas.length} filas)`;sel.append(o);});
  sel.disabled=(p.tablas||[]).length<2;tablaActual=Math.min(tablaActual,Math.max(0,(p.tablas||[]).length-1));sel.value=tablaActual;
  $('confirmed').checked=Boolean(confirmadas[clave()]);
  $('desde-texto').hidden=!p.texto;
  $('image').hidden=!p.imagen;bitmap=null;if(p.imagen){const index=current;const im=new Image();im.onload=()=>{if(index===current){bitmap=im;paint();}};im.src=p.imagen;}
  renderTabla();
 }
 function renderIndice(data){
  const lista=$('indice-lista');lista.replaceChildren();
  if(!data.indice||data.indice.length<=data.paginas_seleccionadas.length){$('indice').hidden=true;return;}
  $('indice').hidden=false;
  $('indice-resumen').textContent=`El documento tiene ${data.paginas_totales} páginas${data.paginas_totales>data.limite_paginas_texto?` (se listan las primeras ${data.limite_paginas_texto})`:''}. Se leyeron ${data.paginas_seleccionadas.length}, empezando por las que parecen tener cuadros. Elegí hasta ${data.limite_paginas_por_lectura} y volvé a leer; las páginas escaneadas usan OCR (hasta ${data.limite_paginas_ocr}).`;
  for(const p of data.indice){const l=document.createElement('label');const c=document.createElement('input');c.type='checkbox';c.value=p.pagina;c.checked=data.paginas_seleccionadas.includes(p.pagina);l.append(c,` Página ${p.pagina} · ${p.con_texto?'con texto':'escaneada (OCR)'}${p.titulo?' · '+p.titulo:''}`);lista.append(l);}
 }
 async function leer(paginas){
  file=$('file').files[0]||file;if(!file)return;
  if(file.size>15*1024*1024){$('status').textContent='El archivo supera 15 MB.';return;}
  $('read').disabled=true;$('leer-elegidas').disabled=true;$('status').textContent='Leyendo en este servidor. Puede tardar hasta dos minutos…';
  try{const form=new FormData();form.append('archivo',file,file.name);if(paginas)form.append('paginas',paginas.join(','));
   const response=await fetch('/api/ocr/leer',{method:'POST',body:form});const data=await response.json();
   if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'No se pudo completar la lectura.');
   if(!Array.isArray(data.paginas)||!data.paginas.length)throw new Error('La respuesta no contiene páginas legibles para revisar.');
   result=data;current=0;tablaActual=0;for(const k of Object.keys(tablas))delete tablas[k];for(const k of Object.keys(confirmadas))delete confirmadas[k];
   $('pages').replaceChildren();
   data.paginas.forEach((p,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`Página ${p.pagina} · ${p.lectura||estadoLegible(p)} · ${(p.tablas||[]).length} ${(p.tablas||[]).length===1?'tabla':'tablas'}`;$('pages').append(o);});
   const primera=data.paginas.findIndex(p=>(p.tablas||[]).length);if(primera>0){current=primera;$('pages').value=primera;}
   $('coverage').textContent=`${data.paginas_incluidas} de ${data.paginas_totales} páginas en esta lectura. ${data.cobertura_parcial?'Hay páginas sin leer o sin revisar: elegilas arriba si las necesitás.':'Todas las páginas incluidas; falta tu revisión.'}`;
   renderIndice(data);$('review').hidden=false;$('status').textContent=data.alcance;show();
   if(!$('precargado').hidden)$('precargado').textContent=`Archivo traído desde Multilente: ${data.archivo}.`;
   (paginas?$('review'):($('indice').hidden?$('review'):$('indice'))).scrollIntoView({block:'start'});
  }catch(error){$('status').textContent='No se pudo completar la lectura: '+error.message;window.mostrarErrorPersistente?.($('status').textContent);}
  finally{$('read').disabled=false;$('leer-elegidas').disabled=false;}
 }
 $('form').addEventListener('submit',e=>{e.preventDefault();if(result&&!window.confirm('Una nueva lectura reemplaza esta revisión. ¿Ya guardaste lo necesario?'))return;file=null;leer();});
 $('leer-elegidas').addEventListener('click',()=>{const el=[...$('indice-lista').querySelectorAll('input:checked')].map(c=>Number(c.value));if(!el.length){$('status').textContent='Elegí al menos una página.';return;}if(el.length>result.limite_paginas_por_lectura){$('status').textContent=`Elegí hasta ${result.limite_paginas_por_lectura} páginas.`;return;}leer(el);});
 $('grid').addEventListener('input',e=>{const el=e.target.closest('[data-i]');if(!el)return;const t=tabla();const i=Number(el.dataset.i),j=Number(el.dataset.j);if(i<0)t.encabezado[j]=el.textContent;else t.filas[i][j]=el.textContent;desconfirmar();clearTimeout(timer);timer=setTimeout(marcarDudas,300);});
 $('grid').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();e.target.blur();}});
 $('formato').addEventListener('change',()=>{const t=tabla();t.formato=$('formato').value;desconfirmar();marcarDudas();});
 $('completar').addEventListener('click',()=>{const t=tabla();t.filas=completarHaciaAbajo(t.filas,Number($('col-completar').value));desconfirmar();renderTabla();});
 $('add-row').addEventListener('click',()=>{const t=tabla();t.filas.push(Array(t.encabezado.length).fill(''));desconfirmar();renderTabla();});
 $('unir-btn').addEventListener('click',()=>{const t=tabla();const [pi,ti]=$('unir').value.split(':').map(Number);const k=`${pi}:${ti}`;const o=tablas[k]||result.paginas[pi].tablas[ti];t.filas.push(...o.filas.map(f=>f.slice()));desconfirmar();renderTabla();});
 $('desde-texto').addEventListener('click',()=>{const p=result.paginas[current];const x=tablaDesdeTexto(p.texto);p.tablas=(p.tablas||[]).concat([{titulo:'Armada con el texto leído',encabezado:x.encabezado,filas:x.filas,formato_numerico:detectarFormato(x.filas),notas:[]}]);tablaActual=p.tablas.length-1;show();});
 $('zoom').addEventListener('click',()=>{const c=$('image');const big=c.style.maxWidth==='none';c.style.maxWidth=big?'100%':'none';$('zoom').textContent=big?'Ampliar imagen':'Ajustar imagen';});
 $('pages').addEventListener('change',()=>{current=Number($('pages').value);tablaActual=0;show();});
 $('tablas').addEventListener('change',()=>{tablaActual=Number($('tablas').value);show();});
 $('confirmed').addEventListener('change',()=>{confirmadas[clave()]=$('confirmed').checked;botones();});
 function validar(t){
  if(!t.filas.some(f=>f.some(c=>limpio(c))))throw new Error('La tabla no tiene filas con datos.');
  if(t.encabezado.length<2)throw new Error('La tabla necesita al menos dos columnas.');
  if(t.encabezado.some(h=>!limpio(h)))throw new Error('Completá los rótulos de las columnas marcadas antes de continuar.');
 }
 $('csv').addEventListener('click',()=>{try{const t=tabla();validar(t);download(nombreRevisado(result.archivo),csvRevisado(t.encabezado,t.filas,t.formato),'text/csv;charset=utf-8');}catch(e){$('status').textContent=e.message;window.mostrarErrorPersistente?.(e.message);}});
 $('analizar').addEventListener('click',async()=>{
  const t=tabla();
  try{validar(t);}catch(e){$('status').textContent=e.message;window.mostrarErrorPersistente?.(e.message);return;}
  const pendientes=celdasDudosas(t.encabezado,t.filas,t.formato).length;
  if(pendientes&&!window.confirm(`Quedan ${pendientes} ${pendientes===1?'celda marcada':'celdas marcadas'} para revisar. ¿Analizar igual?`))return;
  const p=result.paginas[current];const form=new FormData();
  form.append('archivos',new File([csvRevisado(t.encabezado,t.filas,t.formato)],nombreRevisado(result.archivo),{type:'text/csv'}));
  form.append('origen_lectura',(p.metodo==='ocr_local'||t.origen==='ocr')?'revision_ocr':'revision_pdf');form.append('archivo_original',result.archivo);
  const cifras=t.cifras||p.cifras_pagina;if(cifras)form.append('cifras_original',JSON.stringify(cifras));
  $('analizar').disabled=true;$('status').textContent='Enviando la tabla revisada a Multilente…';
  try{const data=await window.prepararYConfirmarInforme(form);
   window.location.href=`/#/informe/${Number(data.informe_id)}`;
  }catch(e){$('status').textContent='No se pudo analizar: '+e.message;botones();}
 });
 $('evidence').addEventListener('click',()=>{download('evidencia-lectura.json',JSON.stringify({...result,exportado_en:new Date().toISOString(),paginas:result.paginas.map((p,i)=>({...p,imagen:undefined,tablas_revisadas:(p.tablas||[]).map((_,ti)=>({...(tablas[`${i}:${ti}`]||{}),confirmada_por_usuario:Boolean(confirmadas[`${i}:${ti}`])}))}))},null,2),'application/json');});
 if(/[?&]desde=analizar\b/.test(location.search)&&typeof indexedDB!=='undefined'){
  tomarArchivoPendiente().then(dato=>{
   if(!dato||!dato.archivo){$('precargado').hidden=false;$('precargado').textContent='Elegí el archivo que querías analizar para leerlo y revisarlo.';return;}
   const f=new File([dato.archivo],dato.nombre,{type:dato.tipo||dato.archivo.type});
   try{const dt=new DataTransfer();dt.items.add(f);$('file').files=dt.files;}catch(_){file=f;}
   file=f;$('precargado').hidden=false;$('precargado').textContent=`Archivo traído desde Multilente: ${dato.nombre}. Se está leyendo.`;leer();
  }).catch(()=>{$('precargado').hidden=false;$('precargado').textContent='No se pudo traer el archivo: elegilo de nuevo para leerlo y revisarlo.';});
 }
}
