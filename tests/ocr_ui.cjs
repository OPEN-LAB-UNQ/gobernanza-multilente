const test=require('node:test');const assert=require('node:assert/strict');
const {tablaOCR,csvOCR}=require('../static/ocr.js');
test('tabla exige estructura consistente',()=>{assert.throws(()=>tablaOCR('texto'));assert.throws(()=>tablaOCR('A\tB\n1'));assert.throws(()=>tablaOCR('A\tA\n1\t2'));assert.deepEqual(tablaOCR('A\tB\n1\t2'),[['A','B'],['1','2']]);});
test('CSV preserva decimales y neutraliza fórmulas',()=>{const csv=csvOCR([['Concepto','Valor'],['=CMD()', '-1.234,50']]);assert.ok(csv.includes("'="));assert.ok(csv.includes('"-1.234,50"'));});
test('CSV escapa comillas',()=>{assert.ok(csvOCR([['A','B'],['Una "nota"','2']]).includes('"Una ""nota"""'));});
const R=require('../static/ocr.js');
test('dudosas: período vacío, sin rótulo, ambiguo y total que no suma (igual que ocr_local.py)',()=>{
 const d=R.celdasDudosas(['Año','','Valor'],[['', 'A','10'],['2001','B','5'],['','Total','18']]);
 const m=new Map(d.map(x=>[x.fila+':'+x.columna,x.motivo]));
 assert.match(m.get('0:0'),/^Período vacío/);assert.match(m.get('-1:1'),/^Columna sin rótulo/);assert.match(m.get('2:2'),/^No suma/);
 assert.ok(R.celdasDudosas(['C','V'],[['a','31,821'],['b','1.054']]).some(x=>/ambiguo/.test(x.motivo)));
 assert.ok(!R.celdasDudosas(['C','V'],[['a','31,821'],['b','1.054']],'en').some(x=>/ambiguo/.test(x.motivo)));
});
test('subtotales no se cuentan dos veces',()=>{
 const d=R.celdasDudosas(['Categoría','2020'],[['Ayuda','30'],['Asig','10'],['Resto','20'],['Salud','5'],['Total General','35']]);
 assert.ok(!d.some(x=>/No suma/.test(x.motivo)));
});
test('completar hacia abajo: rótulo centrado y al comienzo',()=>{
 assert.deepEqual(R.completarHaciaAbajo([['','N'],['2001','P'],['','T'],['','N'],['2002','P'],['','T']],0).map(f=>f[0]),['2001','2001','2001','2002','2002','2002']);
 assert.deepEqual(R.completarHaciaAbajo([['2001','N'],['','P'],['2002','N'],['','P'],['','T']],0).map(f=>f[0]),['2001','2001','2002','2002','2002']);
});
test('CSV revisado: punto y coma, coma decimal, sin miles, nombre (revisado)',()=>{
 const csv=R.csvRevisado(['Concepto','Valor','%','%'],[['=A1','1.234,5','12,5','3'],['B','(2.000)','3','1']],'es');
 assert.ok(csv.startsWith('\uFEFFConcepto;Valor;%;% · %\r\n'));
 assert.ok(csv.includes("'=A1;1234,5;12,5;3")&&csv.includes('B;-2000;3;1'));
 assert.ok(R.csvRevisado(['A','B'],[['x','1,234.56']],'en').endsWith('x;1234,56\r\n'));
 assert.equal(R.nombreRevisado('C:\\docs\\gpsdn_2001-2020.pdf'),'gpsdn_2001-2020 (revisado).csv');
});
