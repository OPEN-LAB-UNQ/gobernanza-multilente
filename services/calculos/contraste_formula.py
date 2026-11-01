"""Contraste acotado de fórmulas vecinas; no ejecuta código ni macros.

Solo documenta el resultado del patrón observado, no afirma que ese patrón sea
la regla autorizada. Fórmulas no admitidas quedan explícitamente sin recalcular.
"""
import ast
import math
import operator
import re

from openpyxl.formula.translate import Translator


def calcular(ws, formula, pila=(), presupuesto=None):
    presupuesto = presupuesto if presupuesto is not None else [1000]
    if len(pila) > 30 or len(str(formula)) > 2000:
        raise ValueError("límite de cálculo")
    if not isinstance(formula, str) or not formula.startswith("="):
        if formula is None:
            raise ValueError("celda vacía")
        return formula
    texto = formula[1:].replace("$", "")
    # El subconjunto no admite rangos, referencias externas, fechas ni macros.
    raiz = ast.parse(texto, mode="eval").body

    def leer(n):
        presupuesto[0] -= 1
        if presupuesto[0] < 0:
            raise ValueError("límite de cálculo")
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str, bool)):
            return n.value
        if isinstance(n, ast.Name) and re.fullmatch(r"[A-Z]{1,3}[1-9][0-9]{0,6}", n.id):
            if n.id in pila:
                raise ValueError("ciclo")
            return calcular(ws, ws[n.id].value, pila + (n.id,), presupuesto)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = leer(n.operand)
            if not isinstance(v, (int, float)):
                raise ValueError("no numérico")
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and type(n.op) in {ast.Add, ast.Sub, ast.Mult, ast.Div}:
            a, b = leer(n.left), leer(n.right)
            if not all(isinstance(v, (int, float)) for v in (a, b)):
                raise ValueError("no numérico")
            return {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}[type(n.op)](a, b)
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in {ast.GtE, ast.LtE, ast.Gt, ast.Lt, ast.Eq, ast.NotEq}:
            return {ast.GtE: operator.ge, ast.LtE: operator.le, ast.Gt: operator.gt, ast.Lt: operator.lt, ast.Eq: operator.eq, ast.NotEq: operator.ne}[type(n.ops[0])](leer(n.left), leer(n.comparators[0]))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
            if n.func.id == "IF" and len(n.args) == 3:
                return leer(n.args[1] if leer(n.args[0]) else n.args[2])
            if n.func.id == "AND" and n.args:
                return all(leer(a) for a in n.args)
        raise ValueError("fórmula fuera del subconjunto admitido")
    valor = leer(raiz)
    if isinstance(valor, (int, float)) and not math.isfinite(valor):
        raise ValueError("resultado no finito")
    return valor


def enriquecer(ws, hallazgos):
    from services.calculos.excel_utils import _formula_cells_col, _patron_mayoritario
    for h in hallazgos:
        ev = h.get("evidencia") or {}
        if ev.get("regla") not in {"formula_fuera_de_patron", "valor_fijo_en_serie_de_formulas"} or ev.get("eje") != "columna":
            continue
        destino = ws[ev["celda"]]
        formulas = _formula_cells_col(ws, destino.column)
        patron, _ = _patron_mayoritario(formulas)
        fuentes = [(r, f) for r, f, normal in formulas if normal == patron]
        if not fuentes:
            continue
        fila, formula = fuentes[0]
        try:
            referencia = Translator(formula, origin=ws.cell(fila, destino.column).coordinate).translate_formula(destino.coordinate)
            ev["formula_referencia"] = referencia
            ev["origen_formula_referencia"] = f"{ws.title}!{ws.cell(fila, destino.column).coordinate}"
            esperado = calcular(ws, referencia, (destino.coordinate,))
            ev["entradas_recalculo"] = {ref: calcular(ws, ws[ref].value, (destino.coordinate, ref))
                                       for ref in sorted(set(re.findall(r"\b[A-Z]{1,3}[1-9][0-9]*\b", referencia)))
                                       if isinstance(calcular(ws, ws[ref].value, (destino.coordinate, ref)), (int, float))}
            # AVERAGE de un rango de la misma fila: solo celdas numéricas literales.
            actual_formula = destino.value
            match = re.fullmatch(r"=AVERAGE\(([A-Z]+[0-9]+):([A-Z]+[0-9]+)\)", str(actual_formula))
            if match:
                celdas = [c for row in ws[match[1] + ':' + match[2]] for c in row]
                if not celdas or len(celdas) > 1000 or any(not isinstance(c.value, (int, float)) for c in celdas):
                    raise ValueError("rango no numérico")
                actual = sum(c.value for c in celdas) / len(celdas)
            else:
                actual = calcular(ws, actual_formula, (destino.coordinate,))
            ev.update(resultado_actual_recalculado=actual, resultado_patron_recalculado=esperado)
            mismo = abs(actual - esperado) < 1e-9 if all(isinstance(v, (int, float)) for v in (actual, esperado)) else actual == esperado
            ev["resultado_coincide"] = mismo
            h["descripcion"] += f" Resultado observado: {actual}; aplicando el patrón vecino: {esperado}. " + ("El método cambia, pero el resultado de este registro coincide." if mismo else "Los resultados no coinciden; confirmar qué regla corresponde.")
        except (ValueError, TypeError, SyntaxError, KeyError, ZeroDivisionError, OverflowError, RecursionError):
            ev["limite_recalculo"] = "No se recalculó: fórmula fuera del subconjunto seguro o datos insuficientes."
    return hallazgos
