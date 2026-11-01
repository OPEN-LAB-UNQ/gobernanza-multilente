const test=require('node:test');const assert=require('node:assert/strict');
const R=require('../static/ocr.js');
// Igual que tests/test_validacion_externa_1.py (services/ocr_local.py): jerarquía por código y subtotales.
const N={'1':'Deuda','1.1':'Corto','1.1.1':'Bonos','1.1.2':'Préstamos','1.2':'Largo','1.2.1':'Bonos','1.2.2':'Préstamos','2':'Otros','2.1':'Sub','2.2':'Fid','2.3':'Cap'};
function tabla(error){
 const v={'1.1.1':[120,130,125],'1.1.2':[40,45,50],'1.2.1':[900,950,990],'1.2.2':[60,70,80],'2.1':[15,18,20],'2.2':[7,9,11],'2.3':[3,3,4]};
 const suma=(hs)=>[0,1,2].map(j=>hs.reduce((s,h)=>s+v[h][j],0));
 v['1.1']=suma(['1.1.1','1.1.2']);v['1.2']=suma(['1.2.1','1.2.2']);v['2']=suma(['2.1','2.2','2.3']);v['1']=suma(['1.1','1.2']);
 const total=[0,1,2].map(j=>v['1'][j]+v['2'][j]);
 if(error)v[error[0]][error[1]]=error[2];
 const fmt=x=>x.toLocaleString('es-AR');
 const orden=['1','1.1','1.1.1','1.1.2','1.2','1.2.1','1.2.2','2','2.1','2.2','2.3'];
 return [['Concepto','Inicial','Altas','Final'],orden.map(k=>[k+' '+N[k],...v[k].map(fmt)]).concat([['TOTAL',...total.map(fmt)]])];
}
const noSuma=d=>d.filter(x=>/^No suma/.test(x.motivo));
test('jerarquía por código: el TOTAL cierra con el primer nivel (sin «No suma»)',()=>{
 const [enc,filas]=tabla();assert.equal(noSuma(R.celdasDudosas(enc,filas)).length,0);
});
test('jerarquía por código: se marca la subcuenta, no su padre ni el TOTAL',()=>{
 const [enc,filas]=tabla(['1.2',1,40]);const m=noSuma(R.celdasDudosas(enc,filas));
 assert.deepEqual(m.map(x=>[x.fila,x.columna]),[[4,2]]);assert.match(m[0].motivo,/1\.2\.1, 1\.2\.2/);
});
test('subtotales intercalados de varios niveles sin códigos',()=>{
 const filas=[['A','100'],['A1','60'],['A1a','25'],['A1b','35'],['A2','40'],['A2a','15'],['A2b','25'],['B','50'],['B1','20'],['B2','30'],['Total','150']];
 assert.equal(noSuma(R.celdasDudosas(['Concepto','2024'],filas)).length,0);
 filas[10]=['Total','170'];assert.deepEqual(noSuma(R.celdasDudosas(['Concepto','2024'],filas)).map(x=>x.fila),[10]);
});
test('códigos que no son jerarquía',()=>{
 assert.equal(R.codigosJerarquia(['1 Uno','2 Dos','3 Tres','Total']).size,0);
 assert.equal(R.codigosJerarquia(['A Buenos Aires','B Córdoba','C Santa Fe']).size,0);
 assert.equal(R.codigosJerarquia(['1.1 X','1.1 Y','1 Z','1.2 W']).size,0);
 assert.deepEqual([...R.codigosJerarquia(['1 X','1.1 Y','1.2 Z'])],[[0,'1'],[1,'1.1'],[2,'1.2']]);
});
test('desglose parcial («de las cuales») y columna no sumable no marcan (igual que ocr_local.py)',()=>{
 const f1=[['1 Cereales','1.500','4.667'],['1.1 Trigo','1.000','3.000'],['1.2 Maíz','500','8.000'],['2 Oleaginosas','500','2.200'],['2.1 Soja','300','2.000'],['2.2 Girasol','200','2.500']];
 assert.equal(noSuma(R.celdasDudosas(['Concepto','Superficie','Rendimiento'],f1)).length,0);
 const f2=[['1 Personal','100'],['1.1 Planta','60'],['1.2 Contratados','40'],['2 Transferencias','500'],['2.1 de las cuales: becas','80'],['2.2 de las cuales: subsidios','120']];
 assert.equal(noSuma(R.celdasDudosas(['Concepto','Monto'],f2)).length,0);
});
