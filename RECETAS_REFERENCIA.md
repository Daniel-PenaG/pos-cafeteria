# Módulo de Recetas - Guía de Referencia

## Resumen de Cambios

### ✅ Problemas Corregidos

1. **Integridad Referencial**: Las ForeignKeys apuntan correctamente:
   - `receta_insumos.id_receta` → `recetas.id_receta`
   - `receta_insumos.id_insumo` → `insumo.id_insumo`
   - `recetas.id_producto` → `productos.id_producto`

2. **Relaciones ORM**: Back_populates emparejados correctamente:
   - `ProductoModel.recetas` ↔ `RecetaModel.producto`
   - `RecetaModel.insumos` ↔ `RecetaInsumoModel.receta`
   - `InsumoModel.receta_insumos` ↔ `RecetaInsumoModel.insumo`

3. **Margen de Ganancia**: Ahora se lee desde `ConfiguracionModel` con default de 15%

4. **Transacciones**: Se utiliza try/except con rollback en caso de error

5. **Validaciones**: 
   - Producto existe
   - Insumos existen
   - Cantidad > 0
   - Nombre no vacío

6. **Lógica de Cálculo**: Completamente funcional
   - `costo_total = suma(cantidad * costo_unitario)`
   - `precio_venta = costo_total * (1 + margen)`

---

## Estructura de Archivos

```
backend/app/
├── models/
│   ├── __init__.py          [Exporta todos los modelos]
│   └── models.py            [Modelos SQLAlchemy - CORREGIDO]
├── schemas/
│   ├── receta.py            [Esquemas Pydantic - MEJORADO]
│   └── recetas.py           [Archivo antiguo - ignorar]
├── routers/
│   └── recetas.py           [Endpoints - COMPLETAMENTE REFACTORIZADO]
├── services/
│   ├── __init__.py          [NUEVO]
│   └── receta_service.py    [NUEVO - Lógica de negocio centralizada]
└── main.py                  [Ya importa el router correctamente]
```

---

## API Endpoints

### 1. **Listar todas las recetas**
```http
GET /recetas/
```

**Response 200:**
```json
[
  {
    "id_receta": 1,
    "id_producto": 5,
    "nombre": "Café con leche",
    "descripcion": "Café espresso + leche vaporizada",
    "activo": true,
    "costo_total": 1.2,
    "insumos": [
      {
        "id_insumo": 10,
        "nombre_insumo": "Café grano",
        "cantidad": 20.0,
        "costo_unitario": 0.05,
        "subtotal": 1.0
      },
      {
        "id_insumo": 15,
        "nombre_insumo": "Leche",
        "cantidad": 200.0,
        "costo_unitario": 0.001,
        "subtotal": 0.2
      }
    ],
    "precio_venta_producto": 1.38
  }
]
```

---

### 2. **Obtener una receta por ID**
```http
GET /recetas/{id_receta}
```

**Response 200:** [mismo formato que listar]

**Response 404:**
```json
{"detail": "Receta no encontrada"}
```

---

### 3. **Crear una nueva receta**
```http
POST /recetas/
Content-Type: application/json
```

**Request Body:**
```json
{
  "id_producto": 5,
  "nombre": "Café con leche",
  "descripcion": "Café espresso + leche vaporizada",
  "activo": true,
  "insumos": [
    {
      "id_insumo": 10,
      "cantidad": 20.0
    },
    {
      "id_insumo": 15,
      "cantidad": 200.0
    }
  ]
}
```

**Response 201:** [Datos de la receta creada con detalles]

**Response 400:**
```json
{"detail": "La cantidad del insumo {id} debe ser mayor a 0"}
```

**Response 404:**
```json
{"detail": "Producto con ID 5 no existe"}
```

---

### 4. **Actualizar una receta**
```http
PUT /recetas/{id_receta}
Content-Type: application/json
```

**Request Body (todos los campos opcionales):**
```json
{
  "nombre": "Café con leche grande",
  "descripcion": "Versión grande",
  "activo": true,
  "insumos": [
    {
      "id_insumo": 10,
      "cantidad": 25.0
    },
    {
      "id_insumo": 15,
      "cantidad": 250.0
    }
  ]
}
```

**Response 200:** [Datos actualizados]

**Response 404:**
```json
{"detail": "Receta no encontrada"}
```

---

### 5. **Eliminar una receta**
```http
DELETE /recetas/{id_receta}
```

**Response 204:** [Sin contenido]

**Response 404:**
```json
{"detail": "Receta no encontrada"}
```

---

## Flujo de Negocio (POST/PUT)

### Paso 1: Validación
- ✅ Producto existe
- ✅ Cada insumo existe
- ✅ Cantidades > 0

### Paso 2: Cálculo de Costo
```python
costo_total = 0
for insumo in insumos:
    costo_total += insumo.cantidad * insumo.costo_unitario
```

### Paso 3: Obtener Margen
```python
config = db.query(ConfiguracionModel).first()
margen = float(config.margen_ganancia) / 100 if config else 0.15
# Ej: margen = 0.15 (15%)
```

### Paso 4: Calcular Precio de Venta
```python
precio_venta = costo_total * (1 + margen)
# Ej: 1.2 * (1 + 0.15) = 1.38
```

### Paso 5: Guardar y Actualizar
- Crear/Actualizar receta
- Crear/Actualizar receta_insumos
- **Actualizar precio_venta en productos**
- Commit/Rollback

---

## Modelos (SQLAlchemy)

### RecetaModel
```python
class RecetaModel(Base):
    __tablename__ = "recetas"
    id_receta: int (PK)
    id_producto: int (FK → productos.id_producto)
    nombre: str
    descripcion: str (nullable)
    activo: bool (default=True)
    costo_total: Decimal
    
    Relaciones:
    - producto: relationship a ProductoModel
    - insumos: relationship a RecetaInsumoModel (cascade delete)
```

### RecetaInsumoModel
```python
class RecetaInsumoModel(Base):
    __tablename__ = "receta_insumos"
    id: int (PK)
    id_receta: int (FK → recetas.id_receta)
    id_insumo: int (FK → insumo.id_insumo)
    cantidad: Decimal
    
    Relaciones:
    - receta: relationship a RecetaModel
    - insumo: relationship a InsumoModel
```

### InsumoModel
```python
class InsumoModel(Base):
    __tablename__ = "insumo"
    id_insumo: int (PK)
    nombre: str
    unidad: str
    stock_actual: Decimal
    stock_minimo: Decimal
    costo_unitario: Decimal
    
    Relaciones:
    - receta_insumos: relationship a RecetaInsumoModel
    - movimientos: relationship a MovimientoInventarioModel
```

### ConfiguracionModel
```python
class ConfiguracionModel(Base):
    __tablename__ = "configuracion"
    id_configuracion: int (PK)
    margen_ganancia: Decimal (default=15.0)
    fecha_actualizacion: DateTime
```

---

## Esquemas Pydantic

### RecetaCreate
```python
{
    "id_producto": int,
    "nombre": str,
    "descripcion": str (opcional),
    "activo": bool (default=True),
    "insumos": [
        {"id_insumo": int, "cantidad": float > 0},
        ...
    ] # Mínimo 1 insumo
}
```

### RecetaUpdate
```python
{
    "nombre": str (opcional),
    "descripcion": str (opcional),
    "activo": bool (opcional),
    "insumos": [
        {"id_insumo": int, "cantidad": float > 0},
        ...
    ] # Opcional
}
```

### RecetaResponse
```python
{
    "id_receta": int,
    "id_producto": int,
    "nombre": str,
    "descripcion": str,
    "activo": bool,
    "costo_total": float,
    "insumos": [
        {
            "id_insumo": int,
            "nombre_insumo": str,
            "cantidad": float,
            "costo_unitario": float,
            "subtotal": float
        },
        ...
    ],
    "precio_venta_producto": float
}
```

---

## Servicio (RecetaService)

Ubicado en `app/services/receta_service.py`. Centraliza toda la lógica de negocio:

- `obtener_margen_ganancia(db)` - Obtiene margen desde config
- `validar_insumo(id, db)` - Valida que insumo existe
- `validar_producto(id, db)` - Valida que producto existe
- `calcular_costo_total(insumos, db)` - Calcula costo total
- `calcular_precio_venta(costo, margen)` - Calcula precio con margen
- `construir_respuesta_insumo(ri, db)` - Construye detalle de insumo
- `construir_lista_insumos_detalle(receta, db)` - Lista completa de insumos

---

## Ejemplo de Uso Completo (cURL)

### 1. Crear una receta
```bash
curl -X POST "http://localhost:8000/recetas/" \
  -H "Content-Type: application/json" \
  -d '{
    "id_producto": 1,
    "nombre": "Cappuccino",
    "descripcion": "Espresso + leche + espuma",
    "insumos": [
      {"id_insumo": 1, "cantidad": 20},
      {"id_insumo": 2, "cantidad": 150}
    ]
  }'
```

### 2. Obtener la receta
```bash
curl -X GET "http://localhost:8000/recetas/1"
```

### 3. Actualizar insumos (recalcula precio)
```bash
curl -X PUT "http://localhost:8000/recetas/1" \
  -H "Content-Type: application/json" \
  -d '{
    "insumos": [
      {"id_insumo": 1, "cantidad": 25},
      {"id_insumo": 2, "cantidad": 200}
    ]
  }'
```

### 4. Eliminar la receta
```bash
curl -X DELETE "http://localhost:8000/recetas/1"
```

---

## Notas Importantes

1. **Cascada**: Al eliminar una receta, los registros en `receta_insumos` se eliminan automáticamente.

2. **Actualización de Precio**: Cada vez que se crea o actualiza una receta, el `precio_venta` del producto se recalcula automáticamente.

3. **Margen Configurable**: El margen se lee desde la BD. Si no existe registro en `configuracion`, usa 15% por defecto.

4. **Precisión Decimal**: Se usa `Decimal` internamente para evitar errores de punto flotante.

5. **Transacciones**: Todas las operaciones usan transacciones con rollback automático en caso de error.

---

## Testing Recomendado

1. Crear receta con producto inexistente → 404
2. Crear receta con insumo inexistente → 404
3. Crear receta con cantidad = 0 → 400
4. Crear receta válida → 201 + verifica precio_venta calculado
5. Actualizar solo nombre → precio NO cambia
6. Actualizar insumos → precio se recalcula
7. Eliminar receta → verifica que insumos se eliminan
8. Cambiar margen en config → crear receta → verifica nuevo precio
