"""Restaura precio_venta según menú físico (JSON en backend/data/)."""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models.models import ProductoModel

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_MENU_FILE = _DATA_DIR / "precios_menu_coffesong.json"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _token_present(nombre_norm: str, tok: str) -> bool:
    if " " in tok:
        return tok in nombre_norm
    words = nombre_norm.split()
    return tok in words


def rule_matches(nombre_norm: str, rule: dict) -> bool:
    for ex in rule.get("exclude") or []:
        if ex in nombre_norm:
            return False
    for tok in rule.get("tokens") or []:
        if not _token_present(nombre_norm, tok):
            return False
    any_tokens = rule.get("tokens_any")
    if any_tokens and not any(_token_present(nombre_norm, t) for t in any_tokens):
        return False
    return True


def precio_desde_menu(nombre: str, data: dict) -> tuple[Optional[float], str]:
    n = norm(nombre)
    exact = data.get("exact") or {}
    if n in exact:
        return float(exact[n]), "exact"

    best_rule = None
    best_len = -1
    for rule in data.get("rules") or []:
        if not rule_matches(n, rule):
            continue
        score = len(rule.get("tokens") or [])
        if score > best_len:
            best_len = score
            best_rule = rule
    if best_rule:
        return float(best_rule["price"]), f"rule:{best_rule.get('tokens')}"
    return None, ""


def cargar_menu(path: Path | None = None) -> dict:
    p = path or DEFAULT_MENU_FILE
    if not p.is_file():
        raise FileNotFoundError(str(p))
    return json.loads(p.read_text(encoding="utf-8"))


def _cambio_dict(producto: ProductoModel, antes: float, despues: float, origen: str) -> dict:
    return {
        "id_producto": producto.id_producto,
        "nombre": producto.nombre,
        "precio_actual": round(antes, 2),
        "precio_menu": round(despues, 2),
        "origen": origen,
    }


def previsualizar_restauracion_precios_menu(
    db: Session,
    *,
    data: dict | None = None,
    solo_activos: bool = False,
) -> dict:
    menu = data if data is not None else cargar_menu()
    q = db.query(ProductoModel).order_by(ProductoModel.nombre)
    if solo_activos:
        q = q.filter(ProductoModel.activo == True)  # noqa: E712
    productos = q.all()

    cambios: list[dict] = []
    sin_match: list[dict] = []

    for p in productos:
        precio, origen = precio_desde_menu(p.nombre, menu)
        if precio is None:
            sin_match.append(
                {
                    "id_producto": p.id_producto,
                    "nombre": p.nombre,
                    "precio_actual": float(p.precio_venta or 0),
                }
            )
            continue
        actual = float(p.precio_venta or 0)
        if abs(actual - precio) < 0.009:
            continue
        cambios.append(_cambio_dict(p, actual, precio, origen))

    return {
        "version_menu": menu.get("version"),
        "total_productos": len(productos),
        "actualizados": len(cambios),
        "sin_match": len(sin_match),
        "cambios": cambios,
        "sin_match_muestra": sin_match[:50],
    }


def restaurar_precios_desde_menu(db: Session, *, data: dict | None = None) -> dict:
    prev = previsualizar_restauracion_precios_menu(db, data=data)
    cambios = prev["cambios"]
    if not cambios:
        return {
            "version_menu": prev.get("version_menu"),
            "actualizados": 0,
            "cambios": [],
            "sin_match": prev["sin_match"],
        }

    by_id = {c["id_producto"]: c for c in cambios}
    productos = (
        db.query(ProductoModel)
        .filter(ProductoModel.id_producto.in_(list(by_id.keys())))
        .all()
    )
    for p in productos:
        c = by_id[p.id_producto]
        p.precio_venta = Decimal(str(round(c["precio_menu"], 2)))
    db.commit()
    return {
        "version_menu": prev.get("version_menu"),
        "actualizados": len(cambios),
        "cambios": cambios,
        "sin_match": prev["sin_match"],
    }
