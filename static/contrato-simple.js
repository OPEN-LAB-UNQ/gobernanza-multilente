/* Declarar condiciones sin escribir JSON.

   Genera el mismo contrato que antes había que tipear a mano, y lo deja a la vista en el cuadro de
   texto: la persona ve exactamente qué declara y puede seguir editándolo. Si lo edita, las casillas
   dejan de tocarlo y se lo avisa, en lugar de pisar lo que escribió. */
(() => {
  const campos = document.getElementById('contrato-campos');
  const moneda = document.getElementById('contrato-moneda');
  const salida = document.getElementById('contexto-validacion');
  const aviso = document.getElementById('contrato-aviso');
  if (!campos || !moneda || !salida) return;
  let generado = '';
  const declarar = () => {
    const requeridos = campos.value.split(',').map((x) => x.trim()).filter(Boolean);
    const contrato = {};
    if (requeridos.length) contrato.campos_requeridos = requeridos;
    if (moneda.checked) contrato.condiciones_criticas = ['moneda'];
    const texto = Object.keys(contrato).length ? JSON.stringify(contrato) : '';
    const actual = String(salida.value || '').trim();
    if (actual && actual !== generado) {
      if (aviso) aviso.textContent = 'La declaración está editada a mano, así que las casillas ya no la modifican. Vaciá el cuadro de texto si querés volver a generarla.';
      return;
    }
    salida.value = texto;
    generado = texto;
    if (aviso) aviso.textContent = texto ? 'Esto es lo que se declara junto con el archivo. Declarar una condición no verifica la veracidad de los datos.' : '';
  };
  campos.addEventListener('input', declarar);
  moneda.addEventListener('change', declarar);
})();
