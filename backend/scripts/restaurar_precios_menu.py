"""
Restaura precio_venta de productos según menú físico (JSON en data/).

Uso:
  cd backend
  set DATABASE_URL=postgresql://...   # BD directa
  python scripts/restaurar_precios_menu.py --dry-run
  python scripts/restaurar_precios_menu.py --apply

  # Tras desplegar API con el JSON embebido:
  set POS_API_URL=https://pos-cafeteria-api.onrender.com
  set POS_ADMIN_LOGIN=tu_admin
  set POS_ADMIN_PASSWORD=***
  python scripts/restaurar_precios_menu.py --api --dry-run
  python scripts/restaurar_precios_menu.py --api --apply

No modifica recetas ni configuración de margen; si luego cambias insumos/margen,
los precios pueden recalcularse otra vez.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_FILE = ROOT / "data" / "precios_menu_coffesong.json"


def _print_preview(prev: dict) -> None:
    print(f"Menú: {prev.get('version_menu')}")
    print(f"Productos en BD: {prev.get('total_productos')}")
    print(f"Con precio de menú distinto: {prev.get('actualizados')}")
    print(f"Sin regla en menú: {prev.get('sin_match')}")
    print()
    for c in prev.get("cambios") or []:
        print(
            f"  [{c['id_producto']}] {c['nombre']!r}: "
            f"${c['precio_actual']:.2f} -> ${c['precio_menu']:.2f} ({c['origen']})"
        )
    sin = prev.get("sin_match_muestra") or []
    if sin:
        print("\n--- Sin match (revisa nombres o agrega a JSON) ---")
        for row in sin[:40]:
            print(f"  [{row['id_producto']}] {row['nombre']} (${row['precio_actual']:.2f})")
        extra = (prev.get("sin_match") or 0) - len(sin)
        if extra > 0:
            print(f"  ... y {extra} más")


def _apply_db(dry: bool, data_path: Path) -> int:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("Define DATABASE_URL (PostgreSQL de Render o sqlite local).", file=sys.stderr)
        return 1

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.services.precio_menu_service import (
        cargar_menu,
        previsualizar_restauracion_precios_menu,
        restaurar_precios_desde_menu,
    )

    data = cargar_menu(data_path)
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        prev = previsualizar_restauracion_precios_menu(db, data=data)
        _print_preview(prev)
        if dry:
            print("\nModo dry-run: no se guardó nada. Usa --apply para aplicar.")
            return 0
        if not prev["actualizados"]:
            print("\nNada que actualizar.")
            return 0
        out = restaurar_precios_desde_menu(db, data=data)
        print(f"\nActualizados {out['actualizados']} productos.")
        return 0
    finally:
        db.close()


def _apply_api(dry: bool) -> int:
    import httpx

    base = (os.getenv("POS_API_URL") or "https://pos-cafeteria-api.onrender.com").rstrip("/")
    login = os.getenv("POS_ADMIN_LOGIN") or os.getenv("LOCAL_ADMIN_LOGIN")
    password = os.getenv("POS_ADMIN_PASSWORD") or os.getenv("LOCAL_ADMIN_PASSWORD")
    if not login or not password:
        print(
            "Define POS_ADMIN_LOGIN y POS_ADMIN_PASSWORD (usuario ADMIN en producción).",
            file=sys.stderr,
        )
        return 1

    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{base}/auth/login", json={"usuario_login": login, "password": password})
        if r.status_code != 200:
            print(f"Login falló ({r.status_code}). Revisa usuario/contraseña.", file=sys.stderr)
            return 1
        token = r.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        path = "/productos/restaurar-precios-menu"
        if dry:
            resp = client.get(f"{base}{path}", headers=headers)
        else:
            resp = client.post(f"{base}{path}", headers=headers)
        if resp.status_code == 404:
            print(
                "El servidor aún no tiene /restaurar-precios-menu. "
                "Despliega el backend o usa --apply con DATABASE_URL.",
                file=sys.stderr,
            )
            return 1
        if resp.status_code >= 400:
            print(f"API error {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
            return 1
        prev = resp.json()
        _print_preview(prev)
        if dry:
            print("\nModo dry-run (--api): no se guardó nada. Usa --apply para aplicar.")
        else:
            print(f"\nActualizados {prev.get('actualizados', 0)} productos (API).")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Restaurar precios desde menú físico")
    parser.add_argument("--apply", action="store_true", help="Escribir cambios")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar (por defecto)")
    parser.add_argument("--api", action="store_true", help="Usar API desplegada (JWT admin)")
    parser.add_argument("--data", type=Path, default=DATA_FILE, help="JSON de precios (solo BD)")
    args = parser.parse_args()
    dry = not args.apply

    if args.api:
        return _apply_api(dry)
    if not args.data.is_file():
        print(f"No existe {args.data}", file=sys.stderr)
        return 1
    return _apply_db(dry, args.data)


if __name__ == "__main__":
    raise SystemExit(main())
