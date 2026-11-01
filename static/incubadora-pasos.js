/* Navegación visual: cambia el bloque visible, sin enviar ni reemplazar borradores. */
(() => {
  const root = document.getElementById('incubadora-personal');
  if (!root) return;
  const definiciones = [
    ['definir', '1. Definir el problema', 'Escribí el contexto y guardalo para empezar.'],
    ['desarrollar', '2. Desarrollar la propuesta', 'Retomá la conversación o consultá al docente.'],
    ['entregar', '3. Revisar y entregar', 'Revisá tu propuesta, guardá el borrador y registrá la entrega cuando lo decidas.'],
    ['opcional', 'Herramientas opcionales', 'El método, R-1 y el seguimiento tienen un alcance separado. No son pasos obligatorios para entregar.'],
  ];
  const nav = document.createElement('nav'); nav.className = 'incubadora-pasos'; nav.setAttribute('aria-label','Bloques de trabajo de Incubadora');
  const status = document.createElement('p'); status.id = 'incubadora-paso-estado'; status.setAttribute('role','status');
  const panels = {};
  for (const [key, title] of definiciones) {
    const button = document.createElement('button'); button.type='button'; button.className='btn btn-secondary';
    button.dataset.incubadoraPaso=key; button.id='paso-boton-'+key; button.textContent=title; button.setAttribute('aria-controls','paso-panel-'+key); nav.append(button);
    const panel=document.createElement('section'); panel.id='paso-panel-'+key; panel.dataset.pasoPanel=key;
    panel.setAttribute('aria-labelledby',button.id); panels[key]=panel;
  }
  const move = (selector,key) => { root.querySelectorAll(selector).forEach(el=>panels[key].append(el)); };
  move(':scope > .project-workspace:not(.project-workspace-chat)','definir');
  move(':scope > .project-workspace-chat','desarrollar');
  move(':scope > .project-clarity-card, :scope > .project-submit-card','entregar');
  move(':scope > details, :scope > .project-stage-strip, :scope > .pilot-governance-card','opcional');
  const anchor=document.getElementById('proyecto-escucha-estado'); anchor.after(nav,status);
  Object.values(panels).forEach(panel=>root.append(panel));
  const memory=new Map(); let current='definir', identity=null;
  function mostrar(key, focus=false) {
    if (!panels[key]) return;
    current=key; if(identity!==null) memory.set(identity,key);
    for(const [k,panel] of Object.entries(panels)) panel.hidden=k!==key;
    nav.querySelectorAll('button').forEach(btn=>{ const selected=btn.dataset.incubadoraPaso===key; btn.setAttribute('aria-pressed',String(selected)); if(selected)btn.setAttribute('aria-current','step');else btn.removeAttribute('aria-current');});
    status.textContent=definiciones.find(x=>x[0]===key)[2]+' Cambiar de bloque conserva lo escrito; usá Guardar para registrarlo.';
    if(focus){status.tabIndex=-1;status.focus();}
  }
  window.mostrarPasoIncubadoraPara = id => {
    const target=document.getElementById(id), panel=target?.closest('[data-paso-panel]');
    if(panel) mostrar(panel.dataset.pasoPanel);
  };
  window.actualizarPasosIncubadora = data => {
    if(!data)return;
    const key=String(state.currentUser?.id || '')+':'+String(data.id || 'nuevo');
    if(key!==identity){identity=key;mostrar(memory.get(key)||(['entregado','revisado'].includes(data.estado)?'entregar':data.mensajes?.length?'desarrollar':'definir'));}
  };
  nav.addEventListener('click',e=>{const b=e.target.closest('[data-incubadora-paso]');if(b)mostrar(b.dataset.incubadoraPaso,true);});
  // Abre el bloque antes de que los accesos existentes desplacen o enfoquen su destino.
  root.addEventListener('click',e=>{
    const b=e.target.closest('[data-scroll-target],#btn-mi-devolucion,[data-segunda-vuelta]');
    if(b)window.mostrarPasoIncubadoraPara(b.dataset.scrollTarget || (b.hasAttribute('data-segunda-vuelta') ? 'proyecto-mensaje' : 'proyecto-entrega'));
  },true);
  for(const [index,[key]] of definiciones.entries()){
    if(key==='opcional')continue;
    const footer=document.createElement('div');footer.className='actions-row';
    for(const [dest,label] of [[index-1,'Anterior'],[index+1,'Continuar']]){
      if(dest<0||dest>2)continue;
      const b=document.createElement('button');b.type='button';b.className='btn btn-secondary';b.textContent=label+' · '+definiciones[dest][1];
      b.onclick=()=>mostrar(definiciones[dest][0],true);footer.append(b);
    }panels[key].append(footer);
  }
  mostrar(current);window.actualizarPasosIncubadora(state.proyectoIA);
})();
