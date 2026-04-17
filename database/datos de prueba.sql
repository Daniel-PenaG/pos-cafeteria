INSERT INTO categorias (nombre) VALUES ('Bebidas calientes');
INSERT INTO categorias (nombre) VALUES ('Bebidas frías');
INSERT INTO categorias (nombre) VALUES ('Postres');

INSERT INTO insumos (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
VALUES ('Café en grano', 'g', 1000, 200, 0.20);

INSERT INTO insumos (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
VALUES ('Leche entera', 'ml', 5000, 1000, 0.01);

INSERT INTO insumos (nombre, unidad, stock_actual, stock_minimo, costo_unitario)
VALUES ('Vaso 12oz', 'pieza', 200, 50, 1.00);

INSERT INTO productos (nombre, id_categoria, precio_venta, activo)
VALUES ('Café americano 12oz', 1, 35.00, TRUE);

INSERT INTO recetas (id_producto, id_insumo, cantidad_por_producto)
VALUES (1, 1, 15);

INSERT INTO recetas (id_producto, id_insumo, cantidad_por_producto)
VALUES (1, 3, 1);

INSERT INTO usuarios (nombre, usuario_login, hash_password, rol)
VALUES ('Administrador', 'admin', 'admin', 'ADMIN');
