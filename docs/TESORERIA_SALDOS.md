# Tesorería y saldos por ubicación

Fase 3C. Rama `feature/tesoreria-saldos`, creada desde `origin/main` `d2833727d461cf5add398a03da2f8f3817958402`.

Tesorería responde cuánto dinero del negocio hay en la cafetería, en casa y en el banco. El saldo de cada cuenta es la suma de entradas menos la suma de salidas. El frontend no escribe saldos. El usuario sale del JWT.

## Diagnóstico

Antes de esta fase no existía un libro por ubicación. El dinero quedaba repartido en varios registros que no se suman entre sí.

| Hecho | Dónde queda hoy |
| --- | --- |
| Forma de pago del ticket | `ventas.forma_pago` (`EFECTIVO`, `TRANSFERENCIA`, `TARJETA`, `PUNTOS`, `MIXTO`) |
| Importe monetario | `venta_pagos`. Un componente `PUNTOS` y, si queda remanente, un componente monetario con `importe_monetario` |
| Cobro de mesa, para llevar y Comandera | El pedido se cobra en `pedido_service` y la venta se confirma en `registrar_venta` |
| Caja | `sesiones_caja` y `movimientos_caja` (fondo, gasto de caja, devolución, retiro, ajuste). Es el cajón, no el dinero del negocio en casa o en el banco |
| Compras | `compras` más entrada de inventario. El stock sigue aumentando al crear la compra |
| Gastos | `gastos`. Antes no tenían cuenta ni estado de pago |
| Reportes | Suman ventas y gastos por separado. No conocen traspasos ni saldos por ubicación |
| Migraciones | 002 a 007 se aplican al arrancar. 008 corre después de verificar 007 |

Una venta es exitosa solo cuando `registrar_venta` hace `commit`. En esa misma transacción van inventario, puntos, cierre del pedido, `venta_pagos` y, si Tesorería está activa, la entrada de dinero. Si el movimiento de Tesorería falla, el `rollback` deshace la venta, los puntos, los pagos y el inventario. El pedido sigue abierto.

El cierre de caja no vuelve a insertar la venta. La entrada ya se creó al cobrar, a partir de `venta_pagos`, nunca del total del ticket si una parte se pagó con puntos. El arqueo solo compara lo contado contra lo esperado del cajón.

## Modelo

| Tabla | Papel |
| --- | --- |
| `cuentas_tesoreria` | Tres cuentas de sistema, moneda MXN |
| `operaciones_tesoreria` | Cabecera inmutable. `operation_id` único y `payload_hash` |
| `movimientos_tesoreria` | `ENTRADA` o `SALIDA`. El importe siempre es positivo |
| `activacion_tesoreria` | Una sola fila (`unica = 1`) |
| `conciliaciones_tesoreria` | Sistema contra físico. No mueve saldo por sí sola |

Cuentas iniciales:

| Código | Nombre | Tipo |
| --- | --- | --- |
| `EFECTIVO_CAFETERIA` | Efectivo en cafetería | `EFECTIVO` |
| `EFECTIVO_CASA` | Efectivo del negocio en casa | `EFECTIVO` |
| `BANCO` | Cuenta bancaria | `BANCO` |

No hay cuenta de “terminal por depositar”. Un cobro con terminal entra completo a `BANCO`. La comisión se registra después como `COMISION_BANCARIA`.

## Fórmulas

```text
saldo(cuenta) = Σ ENTRADA − Σ SALIDA
total disponible = saldo(cafetería) + saldo(casa) + saldo(banco)
ingresos del periodo = entradas de tipo VENTA
gastos operativos = salidas de GASTO_OPERATIVO, COMPRA y GASTO_CAJA
gastos financieros = salidas de COMISION_BANCARIA
diferencia de conciliación = saldo físico − saldo del sistema
```

No son dinero: puntos, traspasos, saldo inicial y retiro del propietario. El traspaso se informa una vez, por el lado de la salida, para no contarlo como ingreso. El retiro del propietario puede capturarse en Gastos con clasificación `RETIRO_PROPIETARIO` y no entra al margen operativo.

## Tipos de operación

`SALDO_INICIAL`, `VENTA`, `DEVOLUCION`, `COMPRA`, `GASTO_OPERATIVO`, `GASTO_CAJA`, `TRASPASO`, `APORTACION_PROPIETARIO`, `RETIRO_PROPIETARIO`, `COMISION_BANCARIA`, `AJUSTE_SOBRANTE`, `AJUSTE_FALTANTE`, `REVERSA`.

| Pago en `venta_pagos` | Movimiento |
| --- | --- |
| `EFECTIVO` | Entrada en cafetería |
| `TRANSFERENCIA` | Entrada en banco |
| `TARJETA` o `TERMINAL` | Entrada en banco por el importe monetario |
| `PUNTOS` | Ninguno |
| Puntos más efectivo, transferencia o terminal | Solo el remanente monetario |

## Misma transacción

Deben confirmarse juntos:

- La venta, sus pagos, el inventario, los puntos, el cierre del pedido y la entrada de Tesorería.
- Un gasto o una compra pagados y su salida.
- El pago posterior de un gasto que estaba pendiente y su única salida.
- Un gasto de caja, o una devolución en efectivo del cajón, y su salida.
- Las dos líneas de un traspaso.
- La fila de activación y sus saldos iniciales.
- La revisión de una conciliación cuando el administrador confirma el ajuste.

La auditoría no debe revertir por sí sola la operación de negocio.

## Caja

- Cobrar en efectivo aumenta la cafetería en el momento del cobro.
- Cerrar la caja no crea otra entrada.
- El arqueo deja la diferencia pendiente. No ajusta solo.
- Solo un administrador, con observación, confirma `AJUSTE_SOBRANTE` o `AJUSTE_FALTANTE`.
- Abrir caja con fondo que ya estaba en la cafetería no crea ingreso. Si el fondo declarado no coincide con el saldo, hay advertencia y la apertura sigue.
- Si el fondo llega de casa o del banco, es un `TRASPASO` hacia la cafetería. El cliente antiguo que no envía `origen_fondo` se trata como fondo ya existente.
- Un depósito de efectivo al banco es un traspaso, no una venta.
- Un `RETIRO` del cajón no se convierte solo en traspaso. Hay que registrarlo en Tesorería si el dinero cambió de ubicación.

`GASTO_CAJA` disminuye la cafetería una vez. Si el movimiento de caja trae `id_gasto`, el origen es `GASTO`; si no, `MOVIMIENTO_CAJA`. El índice único de origen impide la segunda salida.

Una compra o un gasto `PENDIENTE` no mueven Tesorería. Al pagarse se elige la cuenta y se genera una salida. El inventario de la compra no cambió de regla: el stock sigue entrando al registrar la compra.

## Activación

008 deja Tesorería apagada. Mientras sigue apagada, el POS cobra como antes y no reconstruye ventas viejas.

La activación pide fecha y hora de corte, efectivo de cafetería, efectivo de casa, saldo bancario, observación y confirmación de un administrador. Cada saldo mayor a cero crea un `SALDO_INICIAL`. Un saldo en cero no genera movimiento porque el importe de un movimiento tiene que ser positivo; la activación sí queda registrada.

Es atómica. La misma `operation_id` con la misma huella devuelve el resultado ya guardado. Otra huella, o una segunda activación distinta, responde 409. Las ventas anteriores al corte no crean movimientos. Los saldos iniciales no son ventas ni ingresos operativos.

## Reversas

No se edita ni se borra un movimiento confirmado. La corrección es una operación `REVERSA` con los movimientos opuestos, ligada a la original. No se revierte dos veces. Una reversa no se revierte por este camino. Solo un administrador, con motivo. Se auditan usuario, fecha, operación original y operación nueva.

## Conciliación

Guarda saldo del sistema, saldo físico y diferencia. No cambia el saldo. La revisión autorizada puede generar el ajuste, con observación y `operation_id`. Un sobrante entra. Un faltante sale, si hay fondos.

## Permisos

Módulo `/tesoreria`.

| Acción | ADMIN | CAJERO | COCINA |
| --- | --- | --- | --- |
| `TESORERIA_VER` | sí | sí | no |
| `TESORERIA_REGISTRAR_GASTO` | sí | sí | no |
| `TESORERIA_TRASPASAR` | sí | no | no |
| `TESORERIA_APORTAR` | sí | no | no |
| `TESORERIA_RETIRAR` | sí | no | no |
| `TESORERIA_CONCILIAR` | sí | no | no |
| `TESORERIA_AJUSTAR` | sí | no | no |
| `TESORERIA_REVERTIR` | sí | no | no |
| `TESORERIA_ACTIVAR` | sí | no | no |

`modulos_json` nulo usa los módulos del rol. Una lista vacía sigue vacía. El backend autoriza cada operación. Ocultar la pantalla no autoriza.

## Orden de bloqueos

El cobro no cambia su orden previo:

1. Sesión de caja, si el cajero tiene una.
2. Pedido.
3. Detalles, por `id_detalle_pedido`.
4. Cliente, si el cobro queda asociado a uno.
5. Cuentas de Tesorería, por `id_cuenta` ascendente, solo si está activa.

En PostgreSQL el paso 5 es `SELECT … FOR UPDATE`. Antes de tomar las cuentas, la misma `operation_id` toma `pg_advisory_xact_lock`. La activación toma primero la clave `tesoreria-activacion` y después la de la operación. Una reversa toma primero la clave de esa operación y bloquea la fila original.

Un traspaso no toma sesión ni pedido. Solo cuentas, de menor a mayor `id`. Por eso no invierte el orden del cobro ni el del cierre. El cierre solo bloquea la sesión. Cancelar solo bloquea pedido y detalle. Dos traspasos en direcciones opuestas toman las cuentas en el mismo orden, así que no se esperan en círculo.

Al disminuir una cuenta, dentro de la transacción: bloquear, recalcular el saldo, rechazar si no alcanza, insertar, confirmar. SQLite no usa `FOR UPDATE`; la regla de fondos se prueba igual y la concurrencia real corre en PostgreSQL desechable.

## Migración 008

Archivos:

- `backend/migrations/008_tesoreria_saldos.up.sql`
- `backend/migrations/008_tesoreria_saldos.down.sql`

El arranque aplica 008 después de verificar 007, mediante `aplicar_migracion_008_tesoreria`. Es idempotente. Crea las tres cuentas si no existen. No inserta activación. No reconstruye ventas. Amplía `usuarios.permisos_acciones_json` a `VARCHAR(2000)` porque los códigos nuevos no cabían en 500. Agrega a gastos y compras `estado_pago` y la cuenta, sin tocar 002–007.

`verificar_esquema_tesoreria` impide arrancar si falta una tabla, una columna o una cuenta de sistema, o si hay más de una activación. El error no incluye `DATABASE_URL` ni credenciales.

El DOWN elimina el historial de Tesorería y las columnas nuevas de gastos y compras. Es irrevocable. Solo en una base desechable. No borra ventas, pagos, puntos, caja ni inventario.

## API

Prefijo `/tesoreria`. El usuario es `get_current_user`.

| Método | Ruta |
| --- | --- |
| GET | `/tesoreria/estado` |
| POST | `/tesoreria/activar` |
| GET | `/tesoreria/resumen` |
| GET | `/tesoreria/cuentas` |
| GET | `/tesoreria/movimientos` |
| GET | `/tesoreria/operaciones/{id}` |
| GET | `/tesoreria/reportes` |
| POST | `/tesoreria/traspasos` |
| POST | `/tesoreria/aportaciones` |
| POST | `/tesoreria/retiros` |
| POST | `/tesoreria/comisiones` |
| POST | `/tesoreria/ajustes` |
| POST | `/tesoreria/operaciones/{id}/revertir` |
| GET | `/tesoreria/conciliaciones` |
| POST | `/tesoreria/conciliaciones` |
| POST | `/tesoreria/conciliaciones/{id}/revisar` |

Los movimientos aceptan paginación y filtros de fecha, cuenta, tipo, usuario, origen, referencia y estado. La misma `operation_id` con otra huella responde 409. Un replay devuelve la operación ya guardada.

`POST /gastos/{id}/pagar` paga un gasto pendiente y crea una sola salida. Mientras Tesorería está apagada, el alta de gastos sigue aceptando solo descripción y monto.

## Pantalla

`/tesoreria` muestra el estado inactivo, la activación, las tres cuentas, el total, ingresos, gastos operativos, comisiones, retiros y diferencias pendientes. Desde ahí se registran traspaso, aportación, retiro, comisión, conciliación, ajuste y reversa, según el permiso.

Los importes se muestran en MXN con dos decimales. En 767 px o menos la rejilla es de una columna, los inputs quedan en 16 px y los botones en 44 px. Las tablas van en `table-wrap`. Los modales usan la caja existente, compatible con `100dvh`. No se agregó una librería de UI ni se cambió el diseño de tablet y escritorio que ya existía.

## Auditoría

Se registran activación, traspasos, aportaciones, retiros, comisiones, ajustes, conciliaciones, reversas, saldo insuficiente y conflicto de idempotencia. No se guardan contraseñas, tokens, `DATABASE_URL` ni datos bancarios completos.

## Pruebas

- SQLite aislado: activación, ventas por forma de pago, puntos, mixto, replay, 409, traspaso, cierre, gasto de caja, gasto pendiente y su pago, comisión, retiro, reversa, conciliación, permisos, fallo de Tesorería con rollback de la venta, migración repetida y DOWN sobre el motor desechable.
- PostgreSQL: se omiten sin `POSTGRES_TEST_URL`. La guarda rechaza la misma identidad que `DATABASE_URL`. Sobre una base local desechable cubren 008 dos veces, esquema parcial, conservación de ventas y de `detalle_pedido.sin_promocion`, activación concurrente, dos traspasos sobre el mismo saldo, traspaso contra gasto, cobro contra traspaso, cierre sin duplicar la venta, reversa concurrente, la misma `operation_id`, direcciones opuestas sin deadlock, ausencia de movimientos huérfanos y ausencia de saldo negativo. El DOWN de esas pruebas corre solo en esa base.
- Frontend: formato MXN, saldo visible, validación de traspaso, puntos, remanente mixto, retiro, diferencia, 409, 403 y columnas por ancho.

## Riesgos

- Un retiro del cajón no mueve solo el dinero a casa o al banco.
- La comisión de terminal no se calcula al cobrar. Hay que capturarla.
- Con Tesorería activa, un gasto pagado sin cuenta responde 422. El APK actual sigue operando mientras Tesorería esté apagada.
- La compra pendiente sigue metiendo inventario al crearse. Solo la salida de dinero espera al pago.
- La apertura de caja avisa si el fondo no coincide, pero no bloquea.
- Un saldo inicial en cero no deja movimiento.
- Los reportes históricos de ventas no se reescribieron. Tesorería empieza en el corte.

## Activar en un despliegue futuro

1. Confirmar respaldo recuperable de PostgreSQL.
2. Desplegar el backend. 008 corre sola al arrancar y Tesorería queda apagada. El POS sigue cobrando.
3. Confirmar `GET /health` y que el arranque no reporta esquema 008 incompleto.
4. Desplegar el frontend.
5. Entrar como administrador a `/tesoreria`.
6. Capturar la fecha de corte, el efectivo contado en cafetería, el efectivo en casa, el saldo bancario y una observación.
7. Confirmar. Revisar que existen tres saldos iniciales y que una venta anterior al corte no aparece como movimiento.
8. A partir de ahí, los cobros nuevos alimentan el libro.

No activar dos veces. No correr el DOWN en esa base.

## Rollback

Si 008 aún no se activó y hay que retirar el código: volver al despliegue anterior. Las tablas vacías pueden quedar. No correr el DOWN en producción.

Si ya hubo movimientos, el DOWN borra el historial y no se usa. La corrección de un movimiento es una reversa. Un ajuste de conciliación también deja historia.

Para una base desechable, `008_tesoreria_saldos.down.sql` o `aplicar_down_tesoreria_desechable` eliminan solo Tesorería. Ventas, puntos, caja e inventario permanecen.
