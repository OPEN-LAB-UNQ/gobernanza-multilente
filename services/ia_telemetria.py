"""Diagnóstico por intento. No almacena claves ni cabeceras de autenticación."""

from __future__ import annotations

import hashlib
import json
import re
import time

from services.sanitizacion import redactar_texto_libre


def seguro(valor):
    texto = redactar_texto_libre(str(valor or ""))
    texto = re.sub(r"(?i)\bbearer\s+[^\s,;]+", "Bearer [REDACTADO]", texto)
    texto = re.sub(r"(?i)(api[_-]?key|authorization|bearer|key)([\s=:]+)[^\s&,;]+", r"\1\2[REDACTADO]", texto)
    return texto[:2000]


def iniciar(ctx, prompt):
    sem = ctx.get("_semantica_enviada") or {}
    ctx["_telemetria"] = {
        "status": "started",
        "error_type": None,
        "http_status": None,
        "latency": None,
        "input_tokens": None,
        "input_tokens_source": "no_informado",
        "input_bytes": len(prompt.encode()),
        "input_elements": len(sem.get("elementos", [])),
        "input_blocks": len(sem.get("bloques", [])),
        "output_tokens": None,
        "output_received": False,
        "output_chars": 0,
        "output_excerpt": None,
        "output_sha256": None,
        "parse_status": "not_attempted",
        "discard_reason": None,
        "finish_reason": None,
    }
    ctx["_inicio_llamada"] = time.monotonic()


def http(ctx, status):
    ctx.setdefault("_telemetria", {})["http_status"] = status


def respuesta(ctx, texto, input_tokens=None, output_tokens=None, finish_reason=None):
    t = ctx.setdefault("_telemetria", {})
    raw = str(texto or "")
    t.update(
        output_received=bool(raw.strip()),
        output_chars=len(raw),
        output_sha256=hashlib.sha256(raw.encode()).hexdigest(),
        output_excerpt=seguro(raw),
        output_truncated_in_log=len(raw) > 2000,
    )
    if input_tokens is not None:
        t.update(input_tokens=input_tokens, input_tokens_source="proveedor")
    if output_tokens is not None:
        t["output_tokens"] = output_tokens
    if finish_reason is not None:
        t["finish_reason"] = str(finish_reason)
    if str(finish_reason).lower() in {"length", "max_tokens", "finishreason.max_tokens", "max_output_tokens"}:
        t.update(
            error_type="token_limit",
            discard_reason="El proveedor alcanzó el límite de salida.",
            parse_status="truncated",
        )


def fallo_parse(ctx, exc):
    t = ctx.setdefault("_telemetria", {})
    mensaje = str(exc)
    tipo = "json_invalid" if isinstance(exc, json.JSONDecodeError) or "objeto JSON" in mensaje else "schema_invalid"
    if any(x in mensaje for x in ["referencia", "citas", "ubicación", "discordancia", "conjunto de hallazgos"]):
        tipo = "reference_invalid"
    if not t.get("output_received"):
        tipo = "empty_response"
    if t.get("error_type") != "token_limit":
        t.update(error_type=tipo, parse_status="invalid")
    t["discard_reason"] = seguro(exc)


def excepcion(ctx, exc):
    t = ctx.setdefault("_telemetria", {})
    if t.get("error_type"):
        return
    status = getattr(exc, "status_code", None) or t.get("http_status")
    nombre = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in nombre or "timeout" in msg or "timed out" in msg:
        tipo = "timeout"
    elif status == 429:
        tipo = "rate_limit"
    elif status in (401, 403):
        tipo = "authentication"
    elif status and status >= 400:
        tipo = "http_error"
    elif isinstance(exc, (json.JSONDecodeError, ValueError, KeyError, TypeError)):
        fallo_parse(ctx, exc)
        return
    elif "connect" in nombre or "network" in nombre:
        tipo = "network_error"
    else:
        tipo = "provider_error"
    t.update(error_type=tipo, http_status=status, discard_reason=seguro(exc))


def finalizar(ctx, it):
    t = ctx.get("_telemetria") or {}
    t["latency"] = round(time.monotonic() - ctx.get("_inicio_llamada", time.monotonic()), 3)
    if it.get("contenido") is not None and not t.get("error_type"):
        t.update(status="completed", parse_status="valid", discard_reason=None)
    else:
        t["status"] = "failed"
        if not t.get("error_type"):
            error = it.get("error") or "Respuesta sin contenido"
            t.update(
                error_type="configuration" if "no configurad" in str(error).lower() else "provider_error",
                discard_reason=seguro(error),
            )
    return dict(t)


def json_http(ctx, resp):
    try:
        return resp.json()
    except (ValueError, TypeError) as exc:
        respuesta(ctx, resp.text)
        t = ctx.setdefault("_telemetria", {})
        t.update(
            error_type="json_invalid" if resp.text.strip() else "empty_response",
            parse_status="invalid",
            discard_reason="El cuerpo HTTP no contiene JSON válido: " + seguro(exc),
        )
        raise
