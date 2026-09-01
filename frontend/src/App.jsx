import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Ventas from "./pages/Ventas";
import MesasActivas from "./pages/MesasActivas";
import Comandera from "./pages/Comandera";
import MainLayout from "./layout";
import ProtectedRoute from "./components/ProtectedRoute";
import RoleRoute from "./components/RoleRoute";
import PageLoader from "./components/PageLoader";
import { getDefaultRoute } from "./config/permissions";
import { useAuthStore } from "./store/authStore";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Productos = lazy(() => import("./pages/Productos"));
const Categorias = lazy(() => import("./pages/Categorias"));
const Recetas = lazy(() => import("./pages/Recetas"));
const VentasParaLlevar = lazy(() => import("./pages/VentasParaLlevar"));
const ParaLlevar = lazy(() => import("./pages/ParaLlevar"));
const Compras = lazy(() => import("./pages/Compras"));
const Gastos = lazy(() => import("./pages/Gastos"));
const Insumos = lazy(() => import("./pages/Insumos"));
const ExtrasVenta = lazy(() => import("./pages/ExtrasVenta"));
const Promociones = lazy(() => import("./pages/Promociones"));
const Clientes = lazy(() => import("./pages/Clientes"));
const Reportes = lazy(() => import("./pages/Reportes"));
const CuentasCajero = lazy(() => import("./pages/CuentasCajero"));
const CierreCaja = lazy(() => import("./pages/CierreCaja"));
const CierresDia = lazy(() => import("./pages/CierresDia"));
const Usuarios = lazy(() => import("./pages/Usuarios"));

function HomeRedirect() {
  const rol = useAuthStore((state) => state.user?.rol);
  const modulos = useAuthStore((state) => state.user?.modulos);
  return <Navigate to={getDefaultRoute(rol, modulos)} replace />;
}

function withRole(path, element) {
  return <RoleRoute path={path}>{element}</RoleRoute>;
}

function LazyPage({ children }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
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
          <Route
            path="dashboard"
            element={withRole("/dashboard", <LazyPage><Dashboard /></LazyPage>)}
          />
          <Route
            path="categorias"
            element={withRole("/categorias", <LazyPage><Categorias /></LazyPage>)}
          />
          <Route
            path="productos"
            element={withRole("/productos", <LazyPage><Productos /></LazyPage>)}
          />
          <Route
            path="insumos"
            element={withRole("/insumos", <LazyPage><Insumos /></LazyPage>)}
          />
          <Route
            path="recetas"
            element={withRole("/recetas", <LazyPage><Recetas /></LazyPage>)}
          />
          <Route path="ventas" element={withRole("/ventas", <Ventas />)} />
          <Route path="mesas-activas" element={withRole("/mesas-activas", <MesasActivas />)} />
          <Route
            path="ventas-para-llevar"
            element={withRole("/ventas-para-llevar", <LazyPage><VentasParaLlevar /></LazyPage>)}
          />
          <Route
            path="para-llevar"
            element={withRole("/para-llevar", <LazyPage><ParaLlevar /></LazyPage>)}
          />
          <Route path="comandera" element={withRole("/comandera", <Comandera />)} />
          <Route
            path="extras-venta"
            element={withRole("/extras-venta", <LazyPage><ExtrasVenta /></LazyPage>)}
          />
          <Route
            path="promociones"
            element={withRole("/promociones", <LazyPage><Promociones /></LazyPage>)}
          />
          <Route
            path="clientes"
            element={withRole("/clientes", <LazyPage><Clientes /></LazyPage>)}
          />
          <Route
            path="compras"
            element={withRole("/compras", <LazyPage><Compras /></LazyPage>)}
          />
          <Route
            path="gastos"
            element={withRole("/gastos", <LazyPage><Gastos /></LazyPage>)}
          />
          <Route
            path="cierre-caja"
            element={withRole("/cierre-caja", <LazyPage><CierreCaja /></LazyPage>)}
          />
          <Route
            path="reportes"
            element={withRole("/reportes", <LazyPage><Reportes /></LazyPage>)}
          />
          <Route
            path="cuentas-cajero"
            element={withRole("/cuentas-cajero", <LazyPage><CuentasCajero /></LazyPage>)}
          />
          <Route
            path="cierres-dia"
            element={withRole("/cierres-dia", <LazyPage><CierresDia /></LazyPage>)}
          />
          <Route
            path="usuarios"
            element={withRole("/usuarios", <LazyPage><Usuarios /></LazyPage>)}
          />
        </Route>

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
