from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Boolean,
    ForeignKey,
)
from datetime import datetime
from sqlalchemy.orm import relationship
from app.database import Base

# ============================
# CATEGORIAS
# ============================
class CategoriaModel(Base):
    __tablename__ = "categorias"

    id_categoria = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)

    productos = relationship("ProductoModel", back_populates="categoria")
    extras_enlazados = relationship(
        "CategoriaExtraModel",
        back_populates="categoria",
        cascade="all, delete-orphan",
    )


# ============================
# PRODUCTOS
# ============================
class ProductoModel(Base):
    __tablename__ = "productos"

    id_producto = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    precio_venta = Column(Numeric(10, 2), nullable=False)
    activo = Column(Boolean, default=True)

    categoria = relationship("CategoriaModel", back_populates="productos")
    recetas = relationship("RecetaModel", back_populates="producto", cascade="all, delete")
    detalles = relationship("DetalleVentaModel", back_populates="producto")
   


# ============================
# INSUMOS
# ============================
class InsumoModel(Base):
    __tablename__ = "insumos"

    id_insumo = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    unidad = Column(String(20), nullable=False)
    stock_bodega = Column(Numeric(12, 3), default=0)
    stock_cafeteria = Column(Numeric(12, 3), default=0)
    stock_actual = Column(Numeric(12, 3), default=0)  # total = bodega + cafetería
    stock_minimo = Column(Numeric(12, 3), default=0)
    costo_unitario = Column(Numeric(10, 4), default=0)

    receta_insumos = relationship("RecetaInsumoModel", back_populates="insumo")
    movimientos = relationship("MovimientoInventarioModel", back_populates="insumo")


# ============================
# RECETAS
# ============================
class RecetaModel(Base):
    __tablename__ = "recetas"

    id_receta = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(String(300), nullable=True)
    activo = Column(Boolean, default=True)
    costo_total = Column(Numeric(12, 4), default=0)

    producto = relationship("ProductoModel", back_populates="recetas")
    insumos = relationship("RecetaInsumoModel", back_populates="receta", cascade="all, delete")


class RecetaInsumoModel(Base):
    __tablename__ = "receta_insumos"

    id = Column(Integer, primary_key=True, index=True)
    id_receta = Column(Integer, ForeignKey("recetas.id_receta"))
    id_insumo = Column(Integer, ForeignKey("insumos.id_insumo"))
    cantidad = Column(Numeric(12, 3), nullable=False)

    receta = relationship("RecetaModel", back_populates="insumos")
    insumo = relationship("InsumoModel", back_populates="receta_insumos")


# ============================
# USUARIOS
# ============================
class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    usuario_login = Column(String(50), unique=True, nullable=False)
    hash_password = Column(String(255), nullable=False)
    rol = Column(String(30), nullable=False)

    ventas = relationship("VentaModel", back_populates="usuario")


# ============================
# VENTAS
# ============================
class VentaModel(Base):
    __tablename__ = "ventas"

    id_venta = Column(Integer, primary_key=True, index=True)
    fecha_hora = Column(DateTime, nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    numero_mesa = Column(Integer, nullable=False, default=1)
    total = Column(Numeric(10, 2), nullable=False)
    forma_pago = Column(String(30), nullable=False)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    puntos_generados = Column(Integer, nullable=False, default=0)

    usuario = relationship("UsuarioModel", back_populates="ventas")
    cliente = relationship("ClienteModel", back_populates="ventas")
    detalles = relationship("DetalleVentaModel", back_populates="venta")


# ============================
# EXTRAS DE VENTA (catálogo propio, independiente de insumos)
# ============================
class ExtraVentaModel(Base):
    """Catálogo editable de extras; puede crearse a mano o copiando datos de un insumo."""

    __tablename__ = "extras_venta"

    id_extra = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    unidad = Column(String(20), nullable=True)
    cantidad = Column(Numeric(12, 3), nullable=False, default=1)
    costo_unitario = Column(Numeric(10, 4), nullable=False, default=0)
    usar_precio_manual = Column(Boolean, default=False)
    precio_personalizado = Column(Numeric(10, 2), nullable=True)
    precio = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String(30), nullable=False, default="OTRO")
    activo = Column(Boolean, default=True)
    id_insumo_origen = Column(Integer, nullable=True)

    categorias = relationship("CategoriaExtraModel", back_populates="extra")


class CategoriaExtraModel(Base):
    """Qué extras del catálogo aplican a cada categoría de producto."""
    __tablename__ = "categoria_extras"

    id = Column(Integer, primary_key=True, index=True)
    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=False)
    id_extra = Column(Integer, ForeignKey("extras_venta.id_extra"), nullable=False)

    categoria = relationship("CategoriaModel", back_populates="extras_enlazados")
    extra = relationship("ExtraVentaModel", back_populates="categorias")


class DetalleVentaModel(Base):
    __tablename__ = "detalle_venta"

    id_detalle = Column(Integer, primary_key=True, index=True)
    id_venta = Column(Integer, ForeignKey("ventas.id_venta"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    extras_json = Column(String(500), nullable=True)
    id_promocion = Column(Integer, ForeignKey("promociones.id_promocion"), nullable=True)
    precio_original = Column(Numeric(10, 2), nullable=True)
    descuento_unitario = Column(Numeric(10, 2), nullable=True)
    costo_unitario_snapshot = Column(Numeric(10, 4), nullable=True)

    venta = relationship("VentaModel", back_populates="detalles")
    producto = relationship("ProductoModel", back_populates="detalles")
    promocion = relationship("PromocionModel", back_populates="detalles")


# ============================
# PROMOCIONES
# ============================
class PromocionModel(Base):
    __tablename__ = "promociones"

    id_promocion = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(String(300), nullable=True)
    tipo = Column(String(30), nullable=False)  # PORCENTAJE, PRECIO_FIJO, DOS_X_UNO
    valor = Column(Numeric(10, 2), nullable=False)
    activa = Column(Boolean, default=True)
    aplica_toda_tienda = Column(Boolean, default=False)
    fecha_inicio = Column(DateTime, nullable=True)
    fecha_fin = Column(DateTime, nullable=True)
    hora_inicio = Column(String(5), nullable=True)  # HH:MM
    hora_fin = Column(String(5), nullable=True)
    dias_semana = Column(String(20), nullable=True)  # ej. "0,1,2,3,4" lun-vie
    margen_minimo = Column(Numeric(5, 2), nullable=True)

    productos = relationship(
        "PromocionProductoModel", back_populates="promocion", cascade="all, delete-orphan"
    )
    categorias = relationship(
        "PromocionCategoriaModel", back_populates="promocion", cascade="all, delete-orphan"
    )
    detalles = relationship("DetalleVentaModel", back_populates="promocion")


class PromocionProductoModel(Base):
    __tablename__ = "promocion_productos"

    id = Column(Integer, primary_key=True, index=True)
    id_promocion = Column(Integer, ForeignKey("promociones.id_promocion"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)

    promocion = relationship("PromocionModel", back_populates="productos")
    producto = relationship("ProductoModel")


class PromocionCategoriaModel(Base):
    __tablename__ = "promocion_categorias"

    id = Column(Integer, primary_key=True, index=True)
    id_promocion = Column(Integer, ForeignKey("promociones.id_promocion"), nullable=False)
    id_categoria = Column(Integer, ForeignKey("categorias.id_categoria"), nullable=False)

    promocion = relationship("PromocionModel", back_populates="categorias")
    categoria = relationship("CategoriaModel")


# ============================
# MOVIMIENTOS INVENTARIO
# ============================
class MovimientoInventarioModel(Base):
    __tablename__ = "movimientos_inventario"

    id_movimiento = Column(Integer, primary_key=True, index=True)
    id_insumo = Column(Integer, ForeignKey("insumos.id_insumo"), nullable=False)
    tipo = Column(String(10), nullable=False)
    cantidad = Column(Numeric(12, 3), nullable=False)
    motivo = Column(String(30), nullable=False)
    referencia = Column(String(50))
    fecha_hora = Column(DateTime, nullable=False)

    insumo = relationship("InsumoModel", back_populates="movimientos")

class CompraModel(Base):
    __tablename__ = "compras"

    id_compra = Column(Integer, primary_key=True, index=True)
    fecha_hora = Column(DateTime, default=datetime.utcnow)
    proveedor = Column(String(100))
    total = Column(Numeric(10, 2))


class DetalleCompraModel(Base):
    __tablename__ = "detalle_compra"

    id_detalle = Column(Integer, primary_key=True, index=True)
    id_compra = Column(Integer, ForeignKey("compras.id_compra"))
    id_insumo = Column(Integer, ForeignKey("insumos.id_insumo"))
    cantidad = Column(Numeric(10, 2))
    costo_unitario = Column(Numeric(10, 2))
    subtotal = Column(Numeric(10, 2))


# ============================
# CONFIGURACIÓN
# ============================
class ConfiguracionModel(Base):
    __tablename__ = "configuracion"

    id_configuracion = Column(Integer, primary_key=True, index=True)
    margen_ganancia = Column(Numeric(5, 2), default=15.0)  # Porcentaje de margen
    gastos_fijos = Column(Numeric(12, 2), default=1000.0)  # Gastos fijos mensuales
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Configuracion margen={self.margen_ganancia}% gastos={self.gastos_fijos}>"


# ============================
# PEDIDOS / COMANDERA (mesa abierta)
# ============================
class PedidoModel(Base):
    __tablename__ = "pedidos"

    id_pedido = Column(Integer, primary_key=True, index=True)
    numero_mesa = Column(Integer, nullable=False, index=True)
    estado = Column(String(20), nullable=False, default="ABIERTO")  # ABIERTO, COBRADO, CANCELADO
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=True)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    id_venta = Column(Integer, ForeignKey("ventas.id_venta"), nullable=True)
    fecha_apertura = Column(DateTime, nullable=False, default=datetime.utcnow)
    fecha_cierre = Column(DateTime, nullable=True)

    cliente = relationship("ClienteModel")
    detalles = relationship(
        "DetallePedidoModel", back_populates="pedido", cascade="all, delete-orphan"
    )


class DetallePedidoModel(Base):
    __tablename__ = "detalle_pedido"

    id_detalle_pedido = Column(Integer, primary_key=True, index=True)
    id_pedido = Column(Integer, ForeignKey("pedidos.id_pedido"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    nombre_producto = Column(String(150), nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    cantidad_lista = Column(Numeric(10, 2), nullable=False, default=0)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    precio_original = Column(Numeric(10, 2), nullable=True)
    descuento_unitario = Column(Numeric(10, 2), nullable=True)
    id_promocion = Column(Integer, ForeignKey("promociones.id_promocion"), nullable=True)
    nombre_promocion = Column(String(150), nullable=True)
    extras_json = Column(String(500), nullable=True)
    en_comanda = Column(Boolean, default=True)
    fecha_envio_comanda = Column(DateTime, nullable=True)
    fecha_listo_comanda = Column(DateTime, nullable=True)
    line_key = Column(String(120), nullable=False)

    pedido = relationship("PedidoModel", back_populates="detalles")
    producto = relationship("ProductoModel")


# ============================
# FIDELIDAD — CLIENTES
# ============================
class ClienteModel(Base):
    __tablename__ = "clientes"

    id_cliente = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    telefono = Column(String(20), nullable=False, unique=True, index=True)
    codigo_fidelidad = Column(String(20), nullable=False, unique=True, index=True)
    puntos_saldo = Column(Integer, nullable=False, default=0)
    activo = Column(Boolean, default=True)
    fecha_alta = Column(DateTime, nullable=False, default=datetime.utcnow)

    ventas = relationship("VentaModel", back_populates="cliente")
    movimientos = relationship(
        "FidelidadMovimientoModel", back_populates="cliente", cascade="all, delete-orphan"
    )


class FidelidadMovimientoModel(Base):
    __tablename__ = "fidelidad_movimientos"

    id_movimiento = Column(Integer, primary_key=True, index=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=False)
    tipo = Column(String(30), nullable=False)  # ACUMULACION, AJUSTE, REVERSO
    puntos = Column(Integer, nullable=False)
    saldo_despues = Column(Integer, nullable=False)
    id_venta = Column(Integer, ForeignKey("ventas.id_venta"), nullable=True)
    notas = Column(String(300), nullable=True)
    fecha_hora = Column(DateTime, nullable=False, default=datetime.utcnow)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=True)

    cliente = relationship("ClienteModel", back_populates="movimientos")


class FidelidadConfigModel(Base):
    __tablename__ = "fidelidad_config"

    id = Column(Integer, primary_key=True, index=True)
    pesos_por_punto = Column(Numeric(10, 2), nullable=False, default=10.0)
    minimo_compra_acumular = Column(Numeric(10, 2), nullable=False, default=0)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow)
