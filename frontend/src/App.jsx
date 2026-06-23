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
import Promociones from "./pages/Promociones";
import Clientes from "./pages/Clientes";
import Comandera from "./pages/Comandera";
import Reportes from "./pages/Reportes";
import Usuarios from "./pages/Usuarios";
import MainLayout from "./layout";
import ProtectedRoute from "./components/ProtectedRoute";
import RoleRoute from "./components/RoleRoute";
import { getDefaultRoute } from "./config/permissions";
import { useAuthStore } from "./store/authStore";

function HomeRedirect() {
  const rol = useAuthStore((state) => state.user?.rol);
  return <Navigate to={getDefaultRoute(rol)} replace />;
}

function withRole(path, element) {
  return (
    <RoleRoute path={path}>
      {element}
    </RoleRoute>
  );
}

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
          <Route index element={<HomeRedirect />} />
          <Route path="dashboard" element={withRole("/dashboard", <Dashboard />)} />
          <Route path="categorias" element={withRole("/categorias", <Categorias />)} />
          <Route path="productos" element={withRole("/productos", <Productos />)} />
          <Route path="insumos" element={withRole("/insumos", <Insumos />)} />
          <Route path="recetas" element={withRole("/recetas", <Recetas />)} />
          <Route path="ventas" element={withRole("/ventas", <Ventas />)} />
          <Route path="comandera" element={withRole("/comandera", <Comandera />)} />
          <Route path="extras-venta" element={withRole("/extras-venta", <ExtrasVenta />)} />
          <Route path="promociones" element={withRole("/promociones", <Promociones />)} />
          <Route path="clientes" element={withRole("/clientes", <Clientes />)} />
          <Route path="compras" element={withRole("/compras", <Compras />)} />
          <Route path="reportes" element={withRole("/reportes", <Reportes />)} />
          <Route path="usuarios" element={withRole("/usuarios", <Usuarios />)} />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
