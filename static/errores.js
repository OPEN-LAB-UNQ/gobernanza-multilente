/* Avisos persistentes. No reintenta escrituras ni borra formularios. */
(function(root){
'use strict';
function detalleError(detail){
 if(typeof detail==='string')return detail.slice(0,700);
 if(Array.isArray(detail))return detail.map(x=>typeof x==='string'?x:x?.msg||'Dato inválido').join(' · ').slice(0,700);
 if(detail&&typeof detail==='object')return [detail.mensaje,...(Array.isArray(detail.motivos)?detail.motivos:[])].filter(x=>typeof x==='string').join(' · ').slice(0,700);
 return '';
}
if(typeof module!=='undefined')module.exports={detalleError};
if(!root.document)return;
const doc=root.document;
function mostrarError(message){
 const text=detalleError(message)||'No se pudo completar la acción. Intentá nuevamente.';
 let box=doc.getElementById('error-persistente');
 if(!box){
  box=doc.createElement('section');box.id='error-persistente';box.setAttribute('role','alert');box.setAttribute('aria-live','assertive');
  box.style.cssText='position:fixed;bottom:16px;left:12px;right:12px;max-width:850px;margin:auto;z-index:2147483647;background:#fff3ef;color:#572418;border:2px solid #ac3827;border-radius:10px;padding:16px;box-shadow:0 4px 24px #0003;font:16px system-ui;max-height:45vh;overflow:auto;box-sizing:border-box;overflow-wrap:anywhere';
  const title=doc.createElement('strong');title.textContent='No se pudo completar una acción';
  const body=doc.createElement('p');body.id='error-persistente-texto';
  const hint=doc.createElement('p');hint.textContent='El aviso queda visible hasta que lo cierres. Si estabas guardando o enviando, verificá el estado antes de repetir la acción.';hint.style.fontSize='14px';
  const close=doc.createElement('button');close.type='button';close.textContent='Entendido, cerrar aviso';close.style.cssText='font:inherit;padding:9px;border:1px solid #ac3827;border-radius:6px;background:white;color:#572418;cursor:pointer';close.onclick=()=>{box.remove();};
  box.append(title,body,hint,close);(doc.body||doc.documentElement).append(box);
 }
 doc.getElementById('error-persistente-texto').textContent=text;
}
root.mostrarErrorPersistente=mostrarError;
const originalFetch=root.fetch.bind(root);
root.fetch=async function(input,options={}){
 const {estadosEsperados=[],...opcionesFetch}=options;
 let url;try{url=new URL(typeof input==='string'?input:input.url,root.location.href);}catch(_){return originalFetch(input,options);}
 if(url.origin!==root.location.origin||!url.pathname.startsWith('/api/'))return originalFetch(input,options);
 const signal=options.signal||(typeof input==='object'?input.signal:null),controller=new AbortController();let timeout=false;
 const abort=()=>controller.abort();if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
 const timer=root.setTimeout(()=>{timeout=true;controller.abort();},180000);
 try{
  const response=await originalFetch(input,{...opcionesFetch,signal:controller.signal});
  let parsed=null,invalid=false;
  if((response.headers.get('content-type')||'').includes('application/json')&&response.status!==204){
   try{parsed=await response.clone().json();}catch(_){invalid=true;}
  }
  const esperado=String(options.method||(typeof input==='object'?input.method:null)||'GET').toUpperCase()==='GET'&&estadosEsperados.includes(response.status);
  if(!response.ok&&!esperado){
   let msg=response.status===401?'Tu sesión venció o no está disponible. Guardá una copia de tu texto y volvé a ingresar.':response.status===403?'Tu cuenta no tiene permiso para realizar esta acción.':response.status===413?'El archivo supera el tamaño permitido. Probá con uno más pequeño.':response.status>=500?'El servidor no pudo completar la solicitud. Intentá nuevamente en unos minutos.':'La solicitud no pudo completarse.';
   const detail=detalleError(parsed?.detail);if(detail&&response.status!==401&&response.status!==403)msg+=' '+detail;
   mostrarError(msg+' (Código '+response.status+')');
  }else if(invalid){mostrarError('El servidor devolvió una respuesta que la pantalla no pudo interpretar. No se pudo confirmar el resultado.');}
  return response;
 }catch(error){
  if(timeout)mostrarError('La solicitud superó el tiempo de espera. No se pudo confirmar su resultado; verificá el estado antes de repetirla.');
  else if(!signal?.aborted)mostrarError('No se pudo conectar con el servidor. Revisá tu conexión y volvé a intentar la acción.');
  throw error;
 }finally{root.clearTimeout(timer);signal?.removeEventListener('abort',abort);}
};
root.addEventListener('unhandledrejection',()=>mostrarError('Ocurrió un error inesperado al completar la acción. Conservá tu texto y volvé a intentarlo.'));
root.addEventListener('error',event=>{
 if(event.target&&event.target!==root){if(event.target.tagName==='SCRIPT')mostrarError('No se pudo cargar una parte de la pantalla. Guardá tu texto antes de recargar.');return;}
 mostrarError('Una parte de la pantalla dejó de funcionar. Conservá tu texto antes de recargar e intentar nuevamente.');
},true);
})(typeof window!=='undefined'?window:globalThis);
