IF DB_ID('OrdenesDB') IS NULL
    CREATE DATABASE OrdenesDB;
GO

USE OrdenesDB;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

IF OBJECT_ID('dbo.ordenes', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ordenes (
        id      INT IDENTITY(1,1) CONSTRAINT PK_ordenes PRIMARY KEY,
        cliente NVARCHAR(100)  NOT NULL,
        fecha   DATETIME       NOT NULL CONSTRAINT DF_ordenes_fecha DEFAULT GETDATE(),
        estado  NVARCHAR(20)   NOT NULL CONSTRAINT DF_ordenes_estado DEFAULT 'Pendiente',
        total   DECIMAL(14,2)  NOT NULL CONSTRAINT DF_ordenes_total DEFAULT 0,
        CONSTRAINT CK_ordenes_estado CHECK (estado IN ('Pendiente', 'Pagada', 'Anulada'))
    );
END
GO

IF OBJECT_ID('dbo.orden_detalle', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.orden_detalle (
        id              INT IDENTITY(1,1) CONSTRAINT PK_orden_detalle PRIMARY KEY,
        orden_id        INT            NOT NULL,
        producto        NVARCHAR(100)  NOT NULL,
        cantidad        INT            NOT NULL CONSTRAINT CK_detalle_cantidad CHECK (cantidad > 0),
        precio_unitario DECIMAL(12,2)  NOT NULL CONSTRAINT CK_detalle_precio CHECK (precio_unitario >= 0),
        subtotal        AS (cantidad * precio_unitario) PERSISTED,
        CONSTRAINT FK_orden_detalle_ordenes FOREIGN KEY (orden_id)
            REFERENCES dbo.ordenes (id) ON DELETE CASCADE
    );
END
GO

DECLARE @id INT;

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Blanca Perez')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado, fecha) VALUES (N'Blanca Perez', 'Pagada', '2026-11-15T19:40:07');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Monitor 24 pulgadas', 1, 450.00),
        (@id, N'Teclado mecanico', 1, 250.00);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Astrid Castellanos')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado, fecha) VALUES (N'Astrid Castellanos', 'Pendiente', '2026-11-15T19:40:30');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Tablet', 1, 850.00),
        (@id, N'Funda protectora', 3, 17.00);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Gustavo Siu')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado, fecha) VALUES (N'Gustavo Siu', 'Pagada', '2026-11-15T19:43:27');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Laptop', 1, 900.00),
        (@id, N'Mouse inalambrico', 4, 25.00);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Byron Ochoa')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado, fecha) VALUES (N'Byron Ochoa', 'Pendiente', '2026-11-15T20:07:03');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Impresora', 1, 400.00),
        (@id, N'Cartucho de tinta', 4, 50.00);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Juan Perez')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado) VALUES (N'Juan Perez', 'Pendiente');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Laptop', 1, 800.00),
        (@id, N'Mouse inalambrico', 2, 15.50);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Maria Lopez')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado) VALUES (N'Maria Lopez', 'Pagada');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Teclado mecanico', 1, 65.00),
        (@id, N'Monitor 24 pulgadas', 2, 140.00),
        (@id, N'Cable HDMI', 3, 6.75);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Carlos Mejia')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado) VALUES (N'Carlos Mejia', 'Anulada');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Router WiFi', 1, 85.00),
        (@id, N'Switch 8 puertos', 1, 40.00),
        (@id, N'Cable de red Cat6', 5, 3.50);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Ana Rodriguez')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado) VALUES (N'Ana Rodriguez', 'Pendiente');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Audifonos', 2, 45.00),
        (@id, N'Bocina bluetooth', 1, 60.00);
END

IF NOT EXISTS (SELECT 1 FROM dbo.ordenes WHERE cliente = N'Luis Hernandez')
BEGIN
    INSERT INTO dbo.ordenes (cliente, estado) VALUES (N'Luis Hernandez', 'Pagada');
    SET @id = SCOPE_IDENTITY();
    INSERT INTO dbo.orden_detalle (orden_id, producto, cantidad, precio_unitario) VALUES
        (@id, N'Disco duro externo', 1, 70.00),
        (@id, N'Memoria USB 64GB', 3, 9.50);
END

UPDATE o
   SET total = ISNULL((SELECT SUM(d.subtotal) FROM dbo.orden_detalle d WHERE d.orden_id = o.id), 0)
  FROM dbo.ordenes o;
GO