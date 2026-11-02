"""Interfaz web (Flask) para explorar las transacciones normalizadas.

Ejecutar:  python app.py   ->  http://127.0.0.1:5000
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from txnexplorer.audit import write_audit_log
from txnexplorer.filters import SORTS, filter_invalid, filter_transactions
from txnexplorer.loader import load_records
from txnexplorer.metrics import compute_metrics
from txnexplorer.pipeline import run_pipeline
from txnexplorer.rules import load_rules

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
RULES_PATH = BASE / "config" / "rules.json"
LOGS_DIR = BASE / "logs"

app = Flask(__name__)
app.jinja_env.filters["money"] = lambda v, decimals=2: f"{v:,.{decimals}f}"  # decimales segun la moneda
app.jinja_env.filters["pretty"] = lambda v: json.dumps(v, ensure_ascii=False)


def _datasets():
    return sorted(p.name for p in DATA_DIR.glob("*.json"))


def _context():
    """Carga reglas + dataset elegido y ejecuta el pipeline. Devuelve un dict para la plantilla."""
    datasets = _datasets()
    dataset = request.args.get("dataset") or (datasets[0] if datasets else "")
    if dataset not in datasets:  # lista blanca: evita path traversal
        abort(404, "Dataset no encontrado")
    ctx = {"datasets": datasets, "dataset": dataset, "error": None,
           "view": request.args.get("view") if request.args.get("view") in ("invalid", "audit") else "valid",
           "args": request.args}
    try:
        rules = load_rules(RULES_PATH)
        records = load_records(DATA_DIR / dataset)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        ctx.update(error=f"No se pudo cargar los datos o las reglas: {exc}", valid=[], invalid=[], audit=[], metrics=None)
        return ctx
    valid, invalid, audit = run_pipeline(records, rules)
    write_audit_log(audit, LOGS_DIR / f"audit_{Path(dataset).stem}.json", dataset)
    ctx.update(valid=valid, invalid=invalid, audit=audit, metrics=compute_metrics(valid, invalid), rules=rules)
    return ctx


def _filtered_valid(ctx):
    a = request.args
    return filter_transactions(
        ctx["valid"], status=a.get("status", ""), currency=a.get("currency", ""), source=a.get("source", ""),
        q=a.get("q", ""), date_from=a.get("date_from", ""), date_to=a.get("date_to", ""),
        min_amount=a.get("min_amount", ""), max_amount=a.get("max_amount", ""), sort=a.get("sort", "date_desc"),
        review=a.get("review", ""))


@app.route("/")
def index():
    ctx = _context()
    if ctx["error"]:
        return render_template("index.html", **ctx, rows=[], sorts=SORTS)
    if ctx["view"] == "valid":
        rows = _filtered_valid(ctx)
    elif ctx["view"] == "invalid":
        rows = filter_invalid(ctx["invalid"], request.args.get("source", ""), request.args.get("code", ""))
    else:
        rows = ctx["audit"]
    return render_template("index.html", **ctx, rows=rows, sorts=SORTS)


@app.route("/api/transactions")
def api_transactions():
    """Transacciones validas filtradas, en el esquema normalizado (JSON)."""
    ctx = _context()
    if ctx["error"]:
        return jsonify(error=ctx["error"]), 500
    return jsonify([t.to_dict() for t in _filtered_valid(ctx)])


@app.route("/api/audit")
def api_audit():
    ctx = _context()
    if ctx["error"]:
        return jsonify(error=ctx["error"]), 500
    return jsonify([e.to_dict() for e in ctx["audit"]])


@app.route("/api/metrics")
def api_metrics():
    ctx = _context()
    if ctx["error"]:
        return jsonify(error=ctx["error"]), 500
    m = ctx["metrics"]
    m["by_currency"] = {k: {kk: (float(vv) if kk != "count" else vv) for kk, vv in v.items()}
                        for k, v in m["by_currency"].items()}
    return jsonify(m)


if __name__ == "__main__":
    app.run(debug=True)
