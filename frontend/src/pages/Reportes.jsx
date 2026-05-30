import { useState } from "react";
import { getVentasDia, getConsumoInsumos } from "../services/reportesService";

export default function Reportes() {
  const [fecha, setFecha] = useState("");
  const [ventas, setVentas] = useState(null);
  const [consumo, setConsumo] = useState(null);

  const cargar = async () => {
    if (!fecha) return alert("Selecciona una fecha");

    const v = await getVentasDia(fecha);
    const c = await getConsumoInsumos(fecha);

    setVentas(v);
    setConsumo(c);
  };

  return (
    <div>
      <h1>Reportes</h1>

      <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
      <button onClick={cargar}>Cargar</button>

      {ventas && (
        <div>
          <h2>Ventas del día</h2>
          <p>Total: ${ventas.total_dia.toFixed(2)}</p>
          <p>Número de ventas: {ventas.numero_ventas}</p>

          <table>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Cantidad</th>
                <th>Subtotal</th>
                <th>Margen total</th>
              </tr>
            </thead>
            <tbody>
              {ventas.productos.map((p) => (
                <tr key={p.id_producto}>
                  <td>{p.nombre}</td>
                  <td>{p.cantidad}</td>
                  <td>${p.subtotal.toFixed(2)}</td>
                  <td>${p.margen_total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {consumo && (
        <div>
          <h2>Consumo de insumos</h2>

          <table>
            <thead>
              <tr>
                <th>Insumo</th>
                <th>Cantidad consumida</th>
                <th>Stock actual</th>
                <th>Stock mínimo</th>
                <th>Alerta</th>
              </tr>
            </thead>
            <tbody>
              {consumo.consumo.map((i) => (
                <tr key={i.id_insumo}>
                  <td>{i.nombre}</td>
                  <td>{i.cantidad_consumida}</td>
                  <td>{i.stock_actual}</td>
                  <td>{i.stock_minimo}</td>
                  <td>{i.alerta ? "⚠️ Bajo stock" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
