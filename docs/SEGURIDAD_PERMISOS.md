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

| Módulo | Endpoints principales | Default rol | Lectura | Escritura / admin |
|--------|----------------------|-------------|---------|-------------------|
| /ventas, /mesas-activas, /ventas-para-llevar | `/pedidos/*` (salvo cobro comandera), `/ventas/*` | ADMIN, CAJERO | Pedidos y cobro origen VENTAS | Mesas config: ADMIN |
| /comandera | `/comandera/*` | ADMIN, CAJERO, COCINA | Pendientes, marcar listo | Cobro solo con acción |
| /clientes | `/clientes/*` | ADMIN, CAJERO | CRUD clientes | Ajuste puntos y config: ADMIN |
| /productos /categorias /insumos /para-llevar /recetas | `/catalogo/*`, `/recetas/*` | ADMIN (menú) | Quien tenga el módulo o /ventas | Mutaciones: ADMIN |
| /promociones | `/promociones/*` | ADMIN | También /ventas (contexto POS) | CRUD: ADMIN |
| /extras-venta | `/extras-venta/*` | ADMIN | También /ventas | Mutaciones: ADMIN |
| /compras | `/compras/*` | ADMIN | — | ADMIN + módulo |
| /gastos | `/gastos/*` | ADMIN | — | ADMIN + módulo |
| /cierre-caja | `/cierres/resumen`, POST | ADMIN, CAJERO | Propio | Cajero no publica cierre de otro |
| /cierres-dia | `/cierres/` lista | ADMIN | ADMIN | — |
| /reportes /cuentas-cajero /dashboard | `/reportes/*` | según rol | Dashboard cajero (sus ventas) | Reportes admin: ADMIN |
| /usuarios | `/usuarios/*` | ADMIN | — | ADMIN |
| /auditoria | `/auditoria/` | ADMIN | Paginada | Solo lectura |

ADMIN tiene todos los módulos y acciones. Sin `modulos_json` se usan defaults del rol. Frontend y backend usan el mismo catálogo.

**Tener el módulo no implica editar catálogo.** Productos/comandera/ventas: ver matriz.

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
