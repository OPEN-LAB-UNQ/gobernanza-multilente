"""Un solo lugar decide el plural de lo que se cuenta en un texto que lee una persona.

«1 señales» o «1 casos» hacen dudar del resto del informe. La regla es del idioma, no de
cada módulo: por eso vive acá y no repetida en cada reporte.
"""
from typing import Optional


def contar(cantidad, singular: str, plural: Optional[str] = None) -> str:
    """«1 señal», «3 señales», «0 señales»: el número con su sustantivo concordado."""
    cantidad = int(cantidad or 0)
    plural = plural if plural is not None else f"{singular}es" if singular.endswith(("l", "r", "n", "d", "z")) else f"{singular}s"
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def senales(cantidad) -> str:
    """Cómo se cuenta una señal cuando ninguna también es una respuesta posible."""
    cantidad = int(cantidad or 0)
    return "sin señales" if cantidad == 0 else contar(cantidad, "señal", "señales")


def muestra(items, total=None, maximo: int = 5, separador: str = ", ") -> str:
    """Lista citada junto a un conteo: si no entran todos, dice cuántos se muestran.

    «6 celdas (B6, C6, D6, E6, B7)» hace creer que falta una; «… B7; se muestran 5 de 6» no.
    """
    items = [str(x) for x in items]
    total = len(items) if total is None else int(total)
    visibles = items[:maximo]
    texto = separador.join(visibles)
    if total > len(visibles):
        texto += f"; se muestran {len(visibles)} de {total}"
    return texto
