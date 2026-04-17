-- ============================
-- TABLA: categorias
-- ============================
CREATE TABLE categorias (
    id_categoria SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

-- ============================
-- TABLA: productos
-- ============================
CREATE TABLE productos (
    id_producto SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    id_categoria INT NOT NULL,
    precio_venta NUMERIC(10,2) NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);

-- ============================
-- TABLA: insumos
-- ============================
CREATE TABLE insumos (
    id_insumo SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    unidad VARCHAR(20) NOT NULL,
    stock_actual NUMERIC(12,3) DEFAULT 0,
    stock_minimo NUMERIC(12,3) DEFAULT 0,
    costo_unitario NUMERIC(10,4) DEFAULT 0
);

-- ============================
-- TABLA: recetas
-- ============================
CREATE TABLE recetas (
    id_receta SERIAL PRIMARY KEY,
    id_producto INT NOT NULL,
    id_insumo INT NOT NULL,
    cantidad_por_producto NUMERIC(12,3) NOT NULL,
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
    FOREIGN KEY (id_insumo) REFERENCES insumos(id_insumo)
);

-- ============================
-- TABLA: usuarios
-- ============================
CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    usuario_login VARCHAR(50) UNIQUE NOT NULL,
    hash_password VARCHAR(255) NOT NULL,
    rol VARCHAR(30) NOT NULL
);

-- ============================
-- TABLA: ventas
-- ============================
CREATE TABLE ventas (
    id_venta SERIAL PRIMARY KEY,
    fecha_hora TIMESTAMP DEFAULT NOW(),
    id_usuario INT NOT NULL,
    total NUMERIC(10,2) NOT NULL,
    forma_pago VARCHAR(30) NOT NULL,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- ============================
-- TABLA: detalle_venta
-- ============================
CREATE TABLE detalle_venta (
    id_detalle SERIAL PRIMARY KEY,
    id_venta INT NOT NULL,
    id_producto INT NOT NULL,
    cantidad NUMERIC(10,2) NOT NULL,
    precio_unitario NUMERIC(10,2) NOT NULL,
    subtotal NUMERIC(10,2) NOT NULL,
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

-- ============================
-- TABLA: movimientos_inventario
-- ============================
CREATE TABLE movimientos_inventario (
    id_movimiento SERIAL PRIMARY KEY,
    id_insumo INT NOT NULL,
    tipo VARCHAR(10) NOT NULL,
    cantidad NUMERIC(12,3) NOT NULL,
    motivo VARCHAR(30) NOT NULL,
    referencia VARCHAR(50),
    fecha_hora TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (id_insumo) REFERENCES insumos(id_insumo)
);

