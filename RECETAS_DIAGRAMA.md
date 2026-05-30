# Diagrama de Relaciones - Módulo de Recetas

## Estructura de Tablas

```
┌─────────────────────────────────────────────────────────────────┐
│                      BASE DE DATOS                              │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│    CATEGORIAS        │
├──────────────────────┤
│ id_categoria (PK)    │
│ nombre               │
└────────────┬─────────┘
             │
             │ 1:N
             ▼
┌──────────────────────────────────┐
│      PRODUCTOS                   │
├──────────────────────────────────┤
│ id_producto (PK)                 │
│ nombre                           │
│ id_categoria (FK) ───────────────┼──→ CATEGORIAS
│ precio_venta                     │  ◄── SE ACTUALIZA
│ activo                           │     AUTOMÁTICAMENTE
└────────────┬─────────────────────┘
             │
             │ 1:N
             ▼
┌──────────────────────────────────┐
│      RECETAS                     │
├──────────────────────────────────┤
│ id_receta (PK)                   │
│ id_producto (FK) ─────────────────────→ PRODUCTOS
│ nombre                           │
│ descripcion                      │
│ activo                           │
│ costo_total                      │  ◄── CALCULADO
└────────────┬─────────────────────┘     AUTOMÁTICAMENTE
             │
             │ 1:N
             ▼
┌──────────────────────────────────┐
│   RECETA_INSUMOS (Tabla puente)  │
├──────────────────────────────────┤
│ id (PK)                          │
│ id_receta (FK) ────────────────────→ RECETAS
│ id_insumo (FK)  ──┐              │
│ cantidad         │              │
└──────────────────┼──────────────┘
                   │
                   │ N:1
                   ▼
            ┌─────────────────────┐
            │     INSUMO          │
            ├─────────────────────┤
            │ id_insumo (PK)      │
            │ nombre              │
            │ unidad              │
            │ stock_actual        │
            │ stock_minimo        │
            │ costo_unitario      │  ◄── USADO EN CÁLCULOS
            └─────────────────────┘

┌──────────────────────────────────┐
│   CONFIGURACION                  │
├──────────────────────────────────┤
│ id_configuracion (PK)            │
│ margen_ganancia (%)              │  ◄── LEÍDO EN CREACIÓN
│ fecha_actualizacion              │     DE RECETAS
└──────────────────────────────────┘
```

---

## Relaciones ORM (back_populates)

```
ProductoModel.recetas ◄──────────────► RecetaModel.producto
    (1:N)                               (N:1)

RecetaModel.insumos ◄──────────────► RecetaInsumoModel.receta
    (1:N, cascade delete)                (N:1)

InsumoModel.receta_insumos ◄──────────► RecetaInsumoModel.insumo
    (1:N)                               (N:1)
```

---

## Flujo de Creación de Receta

```
┌─ Cliente envía POST /recetas/ ────────────────────────────────┐
│                                                                │
│  {                                                             │
│    "id_producto": 5,                                           │
│    "nombre": "Café con leche",                                 │
│    "insumos": [                                                │
│      {"id_insumo": 10, "cantidad": 20},                        │
│      {"id_insumo": 15, "cantidad": 200}                        │
│    ]                                                           │
│  }                                                             │
└────────────────────┬──────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ 1. VALIDAR PRODUCTO    │
        │   ✓ id_producto = 5    │
        │     existe en BD        │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────┐
        │ 2. VALIDAR INSUMOS     │
        │   ✓ id_insumo 10       │
        │   ✓ id_insumo 15       │
        │   ✓ cantidad > 0       │
        └────────┬───────────────┘
                 │
                 ▼
        ┌────────────────────────────────────┐
        │ 3. CALCULAR COSTO TOTAL            │
        │                                    │
        │   insumo[0]:                       │
        │   cantidad=20, costo_unit=0.05     │
        │   subtotal = 20 * 0.05 = 1.0       │
        │                                    │
        │   insumo[1]:                       │
        │   cantidad=200, costo_unit=0.001   │
        │   subtotal = 200 * 0.001 = 0.2     │
        │                                    │
        │   costo_total = 1.0 + 0.2 = 1.2    │
        └────────┬───────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────────┐
        │ 4. LEER MARGEN DESDE CONFIG        │
        │                                    │
        │   SELECT margen_ganancia           │
        │   FROM configuracion               │
        │                                    │
        │   margen_ganancia = 15.0           │
        │   margen_decimal = 0.15            │
        │   (o default 0.15 si no existe)    │
        └────────┬───────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────────┐
        │ 5. CALCULAR PRECIO_VENTA           │
        │                                    │
        │   precio = costo * (1 + margen)    │
        │   precio = 1.2 * (1 + 0.15)        │
        │   precio = 1.2 * 1.15              │
        │   precio = 1.38                    │
        └────────┬───────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────────┐
        │ 6. GUARDAR EN BD (TRANSACCIÓN)     │
        │                                    │
        │   INSERT INTO recetas (            │
        │     id_producto, nombre, ...       │
        │     costo_total                    │
        │   ) VALUES (5, 'Café...', 1.2)     │
        │   → id_receta = 101                │
        │                                    │
        │   INSERT INTO receta_insumos (     │
        │     id_receta, id_insumo, cantidad │
        │   ) VALUES                         │
        │   (101, 10, 20)                    │
        │   (101, 15, 200)                   │
        │                                    │
        │   UPDATE productos                │
        │   SET precio_venta = 1.38          │
        │   WHERE id_producto = 5            │
        │                                    │
        │   COMMIT                           │
        └────────┬───────────────────────────┘
                 │
                 ▼
┌─ Cliente recibe 201 Created ──────────────────────────────────┐
│                                                                │
│  {                                                             │
│    "id_receta": 101,                                           │
│    "id_producto": 5,                                           │
│    "nombre": "Café con leche",                                 │
│    "costo_total": 1.2,                                         │
│    "insumos": [                                                │
│      {                                                         │
│        "id_insumo": 10,                                        │
│        "nombre_insumo": "Café grano",                          │
│        "cantidad": 20.0,                                       │
│        "costo_unitario": 0.05,                                 │
│        "subtotal": 1.0                                         │
│      },                                                        │
│      {                                                         │
│        "id_insumo": 15,                                        │
│        "nombre_insumo": "Leche",                               │
│        "cantidad": 200.0,                                      │
│        "costo_unitario": 0.001,                                │
│        "subtotal": 0.2                                         │
│      }                                                         │
│    ],                                                          │
│    "precio_venta_producto": 1.38                               │
│  }                                                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Actualización (PUT)

```
Escenario: Cambiar insumos (cantidad diferente)

ANTES:
- Insumo 10: 20 unidades → subtotal 1.0
- Insumo 15: 200 unidades → subtotal 0.2
- costo_total = 1.2
- precio_venta = 1.38

ACTUALIZACIÓN:
{
  "insumos": [
    {"id_insumo": 10, "cantidad": 25},  ← CAMBIO
    {"id_insumo": 15, "cantidad": 250}  ← CAMBIO
  ]
}

DESPUÉS:
1. Valida nuevos insumos ✓
2. Calcula nuevo costo:
   - 25 * 0.05 = 1.25
   - 250 * 0.001 = 0.25
   - costo_total = 1.5 ✓

3. Obtiene margen: 0.15 ✓

4. Calcula nuevo precio:
   - 1.5 * 1.15 = 1.725 ✓

5. Actualiza BD:
   - UPDATE recetas SET costo_total = 1.5
   - DELETE FROM receta_insumos WHERE id_receta = 101
   - INSERT receta_insumos (nuevos datos)
   - UPDATE productos SET precio_venta = 1.725
   - COMMIT ✓

RESULTADO:
- Receta actualizada
- Producto.precio_venta actualizado
- Respuesta con nuevos valores
```

---

## Manejo de Errores

```
┌─ POST /recetas/ ────────────────────────────────────┐
│                                                     │
│ ¿Producto existe?                                   │
│ ├─ NO → 404 "Producto no existe" ──────────────┐   │
│ └─ SÍ                                           │   │
│    │                                            │   │
│    └─ ¿Insumos existen?                         │   │
│       ├─ NO → 404 "Insumo no existe" ──────────┤   │
│       └─ SÍ                                     │   │
│          │                                      │   │
│          └─ ¿Cantidades > 0?                    │   │
│             ├─ NO → 400 "Cantidad debe ser > 0"┤   │
│             └─ SÍ                               │   │
│                │                                │   │
│                └─ Procesa ──────────────────────┤   │
│                   ├─ OK → 201 ✓            ┌───┘   │
│                   │                        │       │
│                   └─ IntegrityError        │       │
│                      → ROLLBACK            │       │
│                      → 400 "Error BD" ──────       │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## Integridad Referencial

```
CASCADE DELETE:
RecetaModel.insumos = relationship(..., cascade="all, delete")

Cuando se elimina una receta:
ANTES:
├── recetas
│   └── id_receta=101
└── receta_insumos
    ├── (101, 10, 20)
    └── (101, 15, 200)

DESPUÉS (DELETE /recetas/101):
├── recetas    ← VACÍO
└── receta_insumos
    └── VACÍO (eliminados automáticamente)

✓ Integridad mantenida
✓ Sin registros huérfanos
```

---

## Almacenamiento de Datos

```
RecetaModel:
┌──────────────────┬──────────────┬────────────────┐
│ id_receta        │ id_producto  │ costo_total    │
├──────────────────┼──────────────┼────────────────┤
│ 101              │ 5            │ 1.2000         │  ← Decimal(12,4)
└──────────────────┴──────────────┴────────────────┘

RecetaInsumoModel:
┌────┬───────────┬──────────┬────────────┐
│ id │ id_receta │ id_insumo│ cantidad   │
├────┼───────────┼──────────┼────────────┤
│ 201│ 101       │ 10       │ 20.000     │  ← Decimal(12,3)
│ 202│ 101       │ 15       │ 200.000    │  ← Decimal(12,3)
└────┴───────────┴──────────┴────────────┘

ProductoModel (ACTUALIZADO):
┌─────────────┬───────────────┐
│ id_producto │ precio_venta  │
├─────────────┼───────────────┤
│ 5           │ 1.38          │  ← Decimal(10,2) - CALCULADO
└─────────────┴───────────────┘
```

---

## Performance

```
Operación: GET /recetas/  (Listar todas)

Query 1: SELECT * FROM recetas
         → Obtiene todas las recetas

Para cada receta:
  Query 2: SELECT * FROM receta_insumos WHERE id_receta = ?
  Query 3: SELECT * FROM insumo WHERE id_insumo = ?
  Query 4: SELECT * FROM productos WHERE id_producto = ?

Mejora posible: Usar eager loading con joinedload()
Pero por ahora es aceptable si no hay miles de recetas.
```
