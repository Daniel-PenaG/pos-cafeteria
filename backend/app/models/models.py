from sqlalchemy import Column, Integer, String, Boolean, Numeric, ForeignKey, TIMESTAMP
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
    recetas = relationship("RecetaModel", back_populates="producto")
    detalles = relationship("DetalleVentaModel", back_populates="producto")


# ============================
# INSUMOS
# ============================
class InsumoModel(Base):
    __tablename__ = "insumos"

    id_insumo = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    unidad = Column(String(20), nullable=False)
    stock_actual = Column(Numeric(12, 3), default=0)
    stock_minimo = Column(Numeric(12, 3), default=0)
    costo_unitario = Column(Numeric(10, 4), default=0)

    recetas = relationship("RecetaModel", back_populates="insumo")
    movimientos = relationship("MovimientoInventarioModel", back_populates="insumo")


# ============================
# RECETAS
# ============================
class RecetaModel(Base):
    __tablename__ = "recetas"

    id_receta = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    id_insumo = Column(Integer, ForeignKey("insumos.id_insumo"), nullable=False)
    cantidad_por_producto = Column(Numeric(12, 3), nullable=False)

    producto = relationship("ProductoModel", back_populates="recetas")
    insumo = relationship("InsumoModel", back_populates="recetas")


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
    fecha_hora = Column(TIMESTAMP, nullable=False)
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"), nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    forma_pago = Column(String(30), nullable=False)

    usuario = relationship("UsuarioModel", back_populates="ventas")
    detalles = relationship("DetalleVentaModel", back_populates="venta")


# ============================
# DETALLE VENTA
# ============================
class DetalleVentaModel(Base):
    __tablename__ = "detalle_venta"

    id_detalle = Column(Integer, primary_key=True, index=True)
    id_venta = Column(Integer, ForeignKey("ventas.id_venta"), nullable=False)
    id_producto = Column(Integer, ForeignKey("productos.id_producto"), nullable=False)
    cantidad = Column(Numeric(10, 2), nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

    venta = relationship("VentaModel", back_populates="detalles")
    producto = relationship("ProductoModel", back_populates="detalles")


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
    fecha_hora = Column(TIMESTAMP, nullable=False)

    insumo = relationship("InsumoModel", back_populates="movimientos")
