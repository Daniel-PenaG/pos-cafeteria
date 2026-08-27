import {
  HiOutlineSquares2X2,
  HiOutlineTag,
  HiOutlineCube,
  HiOutlineArchiveBox,
  HiOutlineDocumentText,
  HiOutlineShoppingCart,
  HiOutlineShoppingBag,
  HiOutlineClipboardDocumentList,
  HiOutlineUserGroup,
  HiOutlineReceiptPercent,
  HiOutlinePlusCircle,
  HiOutlineBanknotes,
  HiOutlineTruck,
  HiOutlineChartBar,
  HiOutlineUsers,
  HiOutlineRectangleStack,
  HiOutlineIdentification,
  HiOutlineViewColumns,
} from "react-icons/hi2";

const ICONS = {
  "/dashboard": HiOutlineSquares2X2,
  "/categorias": HiOutlineTag,
  "/productos": HiOutlineCube,
  "/insumos": HiOutlineArchiveBox,
  "/recetas": HiOutlineDocumentText,
  "/ventas": HiOutlineShoppingCart,
  "/mesas-activas": HiOutlineViewColumns,
  "/ventas-para-llevar": HiOutlineShoppingBag,
  "/comandera": HiOutlineClipboardDocumentList,
  "/clientes": HiOutlineUserGroup,
  "/promociones": HiOutlineReceiptPercent,
  "/extras-venta": HiOutlinePlusCircle,
  "/para-llevar": HiOutlineRectangleStack,
  "/compras": HiOutlineTruck,
  "/gastos": HiOutlineBanknotes,
  "/cierre-caja": HiOutlineBanknotes,
  "/reportes": HiOutlineChartBar,
  "/cuentas-cajero": HiOutlineIdentification,
  "/cierres-dia": HiOutlineClipboardDocumentList,
  "/usuarios": HiOutlineUsers,
};

export default function NavIcon({ to, className = "" }) {
  const Icon = ICONS[to] || HiOutlineSquares2X2;
  return <Icon className={className} aria-hidden />;
}
