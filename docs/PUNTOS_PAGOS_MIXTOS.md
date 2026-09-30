# Fase 3B — Puntos y pagos mixtos

Rama: `feature/puntos-pagos-mixtos`, desde `5313b9a613cf9a92ea634bdc36f7b4b8e728ffd3`.

La implementación está publicada en feature/puntos-pagos-mixtos. Todavía no hay merge a main, despliegue ni migración aplicada en producción.

## Causa raíz de las ventas sin puntos

Hay dos hechos distintos.

El canje no existía: no había redención ni componente PUNTOS. Toda la venta se guardaba como un solo pago del método de cabecera por el total.

La acumulación sí existía y fallaba en un flujo concreto. `registrar_venta` acredita solo si la venta queda con un `id_cliente` activo. El flujo afectado es cobrar con el botón **Cobrar sin cliente**. El request de `POST /pedidos/{id}/cobrar` iba sin `id_cliente` (o en null). Si el pedido ya tenía cliente, el router igual lo ponía en null antes de cobrar, así que `puntos_generados` quedaba en 0. La vista previa no acredita. Cerrar el modal después de un cobro exitoso no revierte el saldo. Mesa, para llevar y comandera usan ese mismo endpoint; no hay otro cobro que pierda al cliente cuando el botón enviado es el de con cliente.

La corrección conserva el cliente del pedido si el cuerpo no lo repite. Quitarlo exige `desasociar_cliente`. Lo demuestran `test_pedido_con_cliente_acumula_aunque_el_cuerpo_no_lo_repita` y `test_quitar_cliente_cobra_sin_puntos_y_no_toca_saldo`.

## Migración 006

Sí existe:

- `backend/migrations/006_puntos_pagos_mixtos.up.sql`
- `backend/migrations/006_puntos_pagos_mixtos.down.sql`

El INSERT de 005 solo agrega un pago monetario cuando la venta no tiene ninguna fila en `venta_pagos`. No actualiza ni borra componentes. Una venta histórica sin pagos sigue recibiendo una fila por el total. Si ya hay PUNTOS, efectivo o ambos, la segunda pasada no crea otra fila ni cambia el remanente. Un importe ya guardado que no cuadre con el total se deja visible.

005 ya tenía `importe_monetario`, `cantidad_puntos`, `equivalencia_puntos` y `operation_id` único. No alcanzaba para impedir:

- dos redenciones o dos acumulaciones de la misma venta;
- dos componentes monetarios;
- un componente PUNTOS con importe distinto de cero;
- repetir un cobro sin una clave de intención.

006, idempotente y sin reescribir historia, agrega:

- `CHECK ck_venta_pago_componente`;
- un solo PUNTOS y un solo componente no-PUNTOS por venta;
- índice único parcial `(id_venta, tipo)` para `REDENCION` y `ACUMULACION`;
- índices por `id_cliente` e `id_venta`;
- tabla `cobro_operaciones`;
- `operation_id` de `venta_pagos` a `VARCHAR(80)` para `{clave}:MONETARIO`.

El backend la aplica y la verifica al arrancar, igual que 002–005. También se puede ejecutar a mano; repetirla es seguro y no reescribe ventas. El relleno de 005 omite una venta que ya tiene cualquier fila en `venta_pagos`, para no crear otro componente si 005 se vuelve a correr.

En PostgreSQL el arranque exige el `CHECK ck_venta_pago_componente`. En SQLite, usada solo en local y en pruebas, no se reconstruye `venta_pagos` para agregar ese `CHECK`: una base nueva lo trae desde el modelo, y una base anterior arranca con los índices únicos y las validaciones del servicio. Esa diferencia no aplica al destino en PostgreSQL.

## venta_pagos

Ticket $120 con 200 puntos y efectivo:

| metodo | importe_monetario | cantidad_puntos | equivalencia_puntos | operation_id |
| --- | --- | --- | --- | --- |
| PUNTOS | 0 | 200 | 20 | `{operation_id}:PUNTOS` |
| EFECTIVO | 100 | null | null | `{operation_id}:MONETARIO` |

`importe_monetario + equivalencia_puntos = total`. No hay una tercera fila con el total.

Pago total con puntos: una fila PUNTOS, importe 0, equivalencia = total, `forma_pago = PUNTOS`, puntos generados 0.

`MIXTO` es solo el resumen de la cabecera. Caja y reportes leen `venta_pagos`. `PUNTOS` y `MIXTO` no entran a efectivo.

## Bloqueos

Orden del cobro, el mismo en Ventas, para llevar y Comandera, con o sin puntos:

1. `SesionCajaModel` `FOR UPDATE`, solo si el cajero tiene sesión
2. `PedidoModel` `FOR UPDATE`
3. `DetallePedidoModel` `FOR UPDATE`, por `id_detalle_pedido`
4. `ClienteModel` `FOR UPDATE`, solo si el cobro queda con cliente
5. alta de `cobro_operaciones`
6. venta, `venta_pagos`, `REDENCION` y `ACUMULACION`, un solo commit

Cancelar una línea toma pedido y después el detalle. No toma la sesión. Cerrar caja toma solo la sesión. El cobro ya no espera la sesión con el pedido tomado.

Si la sesión no está `ABIERTA`, el cobro responde 409 y no descuenta puntos.

Dos dispositivos que gastan el mismo saldo se serializan en el cliente. Si el canje era válido con el saldo leído y otra operación lo consumió, el perdedor recibe 409 `SALDO_PUNTOS_CAMBIO` con el saldo actual. Un request que ya excedía el saldo, el mínimo o el múltiplo de 10 sigue en 422.

## Migración 006 en el arranque

`aplicar_migracion_006_puntos()` corre después de 005. `verificar_esquema_puntos_mixtos()` impide iniciar si falta un índice, la capacidad de `operation_id` o `cobro_operaciones`. En PostgreSQL también exige el `CHECK` físico. No imprime la URL ni credenciales.

Antes del índice único, consulta de solo lectura para ejecutar en el destino antes de publicar:

```sql
SELECT id_venta, tipo, COUNT(*)
FROM fidelidad_movimientos
WHERE id_venta IS NOT NULL
  AND tipo IN ('REDENCION', 'ACUMULACION')
GROUP BY id_venta, tipo
HAVING COUNT(*) > 1;
```

Si hay filas, el arranque se detiene, lista la cantidad de conflictos y los id de venta, y no borra ni consolida movimientos. No arranca con el índice a medias.

Procedimiento administrativo, solo lectura hasta decidir el arreglo:

1. Ejecutar la consulta de arriba en el destino.
2. Anotar `id_venta` y `tipo`. No incluye nombre, teléfono ni credenciales.
3. Revisar cada venta en `fidelidad_movimientos` y dejar una sola `REDENCION` y una sola `ACUMULACION` por venta. El sistema no elige cuál borrar.
4. Volver a iniciar. La migración crea el índice solo si la consulta ya no devuelve filas.

La misma parada aplica si una venta tiene dos componentes `PUNTOS` o dos componentes monetarios. Consulta de diagnóstico:

```sql
SELECT id_venta,
       CASE WHEN metodo = 'PUNTOS' THEN 'PUNTOS' ELSE 'MONETARIO' END AS componente,
       COUNT(*)
FROM venta_pagos
GROUP BY id_venta, CASE WHEN metodo = 'PUNTOS' THEN 'PUNTOS' ELSE 'MONETARIO' END
HAVING COUNT(*) > 1;
```

Tampoco se borran pagos solos. Hay que revisar esas ventas antes de publicar.

## Cliente del pedido

Omitir `id_cliente` en el cobro no borra el cliente del pedido. Para cobrar sin puntos hay que enviar `desasociar_cliente: true`. Eso queda en auditoría como `CLIENTE_DESASOCIADO`.

## Idempotencia

El cobro envía `operation_id`. La huella incluye pedido, cliente, método, puntos y líneas. La misma clave y la misma huella devuelven la misma venta, una redención, una acumulación y los mismos pagos. Otra huella con la misma clave responde 409 y no crea otra venta. Dos cobros intencionales usan dos claves. Sin clave no hay replay; el frontend genera una por intención y la reutiliza solo en reintento de red.

## Caja y reportes

El total del ticket sigue siendo el consumo. El ingreso monetario es la suma de `importe_monetario`. Lo usan el cierre, la sesión, cuentas por cajero, el desglose por método y el ticket de cierre. El arqueo no pide contar puntos. Transferencia y terminal reciben solo su remanente.

## Visual

Capturas locales, sin datos de una persona real, en `docs/screenshots/puntos/`. El cliente de la pantalla es «Cliente demo».

- 390×844, 768×1024 y 1366×768: cliente precargado, pago mixto y pago completo con puntos.
- 390×844: el 409 deja el modal abierto, el pedido en la mesa y el saldo actualizado.

El pie del modal de cobro queda fuera del área que hace scroll, así el botón sigue visible.

## Publicación

006 se aplica sola al arrancar, igual que 002–005. Si el esquema queda incompleto o hay duplicados históricos, el proceso no abre la API. No activar `CAJA_REQUERIDA_PARA_COBRAR`.
