import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Productos from "./pages/Productos";
import Categorias from "./pages/Categorias";
import Recetas from "./pages/Recetas";
import Ventas from "./pages/Ventas";
import Compras from "./pages/Compras";
import Insumos from "./pages/Insumos";
import ExtrasVenta from "./pages/ExtrasVenta";
import MainLayout from "./layout";
import ProtectedRoute from "./components/ProtectedRoute";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="categorias" element={<Categorias />} />
          <Route path="productos" element={<Productos />} />
          <Route path="insumos" element={<Insumos />} />
          <Route path="recetas" element={<Recetas />} />
          <Route path="ventas" element={<Ventas />} />
          <Route path="extras-venta" element={<ExtrasVenta />} />
          <Route path="compras" element={<Compras />} />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
