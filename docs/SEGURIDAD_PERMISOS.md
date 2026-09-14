# Fase 2A — Seguridad, identidad, permisos y auditoría

Rama: `security/permisos-pos`  
Base: `main` (`c13ecfa` estabilidad operativa)  

**No merge. No despliegue. No migraciones en producción.**

---

## 1. Diagnóstico

| Hallazgo | Riesgo |
|----------|--------|
| Roles ADMIN/CAJERO/COCINA + `modulos_json` solo en frontend | Quitar un módulo ocultaba el menú; el endpoint seguía abierto por `require_pos` / `require_kitchen` |
| `id_usuario` en query/body de pedidos, ventas, cobro, puntos | Un cliente podía atribuir operaciones a otra persona |
| Sin estado activo | No se podía invalidar un usuario sin borrarlo |
| Login devolvía 500 con detalle interno | Filtración de errores |
| Sin límite de intentos | Fuerza bruta |
| Sin auditoría | No hay rastro de cobros, logins ni cambios de usuario |

---

## 2. Identidad (decisión)

El backend **siempre** atribuye con `get_current_user()` (JWT).

`id_usuario` del cliente se acepta por compatibilidad con el APK/web actual, **se ignora para atribución**. Si no coincide con el token se registra `ID_USUARIO_DISCREPANCIA` y se usa el usuario autenticado (no 403, para no romper clientes viejos).

CAJERO/COCINA no pueden operar en nombre de otro. No hay impersonación de ADMIN.

---

## 3. Matriz de módulos

La autorización es **por operación**, no por router. Tener uno de varios módulos no abre el resto.

| Operación | Módulo exigido |
|-----------|----------------|
| GET `/pedidos/activos` | `/mesas-activas` **o** `/ventas` |
| GET `/pedidos/mesas` | `/ventas` |
| GET/POST mesa o línea (normal) | `/ventas` |
| GET/POST mesa o línea (para llevar) | `/ventas-para-llevar` |
| PATCH/DELETE línea, cliente, confirmar comanda | Según tipo del pedido ya cargado |
| Cobrar origen VENTAS | `/ventas` o `/ventas-para-llevar` según el pedido |
| Cobrar origen COMANDERA | `/comandera` **y** `COBRAR_DESDE_COMANDERA` |
| POST `/ventas/` | `/ventas` si `para_llevar=false`; `/ventas-para-llevar` si `true` |
| GET `/ventas/extras`, contexto producto | `/ventas` o `/ventas-para-llevar` (sin costos) |
| GET `/catalogo/categorias` | Módulos que necesitan catálogo (ventas, productos, etc.). No `/mesas-activas` |
| Mutar categorías | ADMIN + `/categorias` |
| GET `/catalogo/productos` | `/ventas`, `/ventas-para-llevar` o `/productos` |
| Mutar productos | ADMIN + `/productos` |
| GET/mutar insumos y costos | ADMIN + `/insumos` |
| Productos para llevar | `/para-llevar` (lectura también `/ventas-para-llevar`) |
| Recetas | ADMIN + `/recetas` |
| GET `/extras-venta/tipos` | `/extras-venta`, `/ventas` o `/ventas-para-llevar` |
| Catálogo extras, insumos-importables, configs y costos | ADMIN + `/extras-venta` |
| `/reportes/resumen-dashboard` | `/dashboard` |
| Cuentas por cajero | ADMIN + `/cuentas-cajero` |
| Cierres del día | ADMIN + `/cierres-dia` |
| Resto de `/reportes/*` | ADMIN + `/reportes` |

`/mesas-activas` solo lista pedidos activos. No agrega, edita, elimina ni cobra.

### Semántica de `modulos_json`

| Valor | Efecto |
|-------|--------|
| `null` | Defaults del rol |
| `[]` | Usuario sin módulos (no se convierte a defaults) |

El API **rechaza `[]` con 422** al crear o editar. Para volver a defaults se envía `null`. Frontend y backend usan la misma regla.

ADMIN tiene todos los módulos y acciones. Frontend y backend usan el mismo catálogo.

---

## 4. Permisos de acción

`permisos_acciones_json`: lista normalizada. Hoy: `COBRAR_DESDE_COMANDERA`.

- Valor inicial: vacío (false).
- ADMIN: todas las acciones.
- CAJERO: cobra desde Ventas (`origen=VENTAS`) con módulo de ventas.
- COCINA: solo si tiene la acción y `origen=COMANDERA`.
- Sin permiso: **403**.
- La UI de cobro en Comandera **no está** en esta fase (pendiente fase de pagos). El backend ya valida origen + acción.

---

## 5. Auditoría

Tabla `auditoria`. Fallo de inserción (savepoint) **no revierte** la venta.

No se guardan contraseñas, tokens ni secretos. `sanitizar_detalles` elimina claves prohibidas.

Solo ADMIN consulta (`GET /auditoria/` con paginación y filtros fecha/usuario/acción). Vista simple en `/auditoria`.

---

## 6. Migración 003

Archivos: `backend/migrations/003_usuarios_permisos_auditoria.{up,down}.sql`

Crea: `usuarios.activo` (default true), `permisos_acciones_json`, `ventas.origen_cobro`, tablas `auditoria` y `login_bloqueos`.

Al arrancar, `aplicar_migraciones_sqlite()` replica las mismas sentencias idempotentes. `create_all` también crea las tablas en BD nuevas.

**No se aplicó en producción.**

Verificar: `SELECT activo FROM usuarios LIMIT 5;` → true.  
Revertir: el `.down.sql` (no borra usuarios).

---

## 7. Variables

```
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=5
```

Bloqueo persistido en BD (sirve con varios workers). Sin Redis.

---

## 8. Compatibilidad clientes anteriores

- Siguen pudiendo enviar `id_usuario`; se ignora para atribución.
- Contraseñas existentes no se invalidan; la regla de 8 caracteres aplica a altas y cambios.
- GET mesa / POST líneas no cambian de forma.
- Cobro acepta `origen` opcional (default VENTAS).
- DELETE `/usuarios/{id}` ahora **desactiva** (no borra historial).

---

## 9. Validación manual

1. ADMIN: módulos, usuarios (activar/desactivar), auditoría, cobro desde Ventas.
2. CAJERO: ventas y comandera; sin Usuarios ni reportes admin.
3. COCINA: solo comandera; cobro 403; con permiso, `origen=COMANDERA` autorizado.
4. Usuario inactivo: no entra; token previo → 401 y el frontend limpia sesión.
5. Módulos personalizados: menú y API 403 si se retira el módulo.
6. 403: aviso «No tienes permiso…» sin cerrar sesión.
7. Sidebar: 390 / 768 / 1366 como en Fase 1.

---

## 10. Despliegue futuro (después de revisión)

1. Merge a `main` (no ahora).
2. Arranque aplicará 003; ops puede lanzar el `.up.sql`.
3. Render/Vercel automáticos.
4. Rollback: `.down.sql` + revertir deploy.
5. No Elastic Beanstalk. No APK en esta fase.

---

## 11. Riesgos

- TestClient / multi-worker: el bloqueo de login es por `(usuario_login, ip)`.
- UI de cobro en Comandera pendiente.
- Pago con puntos no implementado.
- SQLite `begin_nested` para auditoría: si falla, se omite el rastro (la venta queda).
