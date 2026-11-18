-- ============================================================
--  PiedPiper Inventario · Esquema relacional (MariaDB 10.4+)
--  Se aplica sobre la base configurada en DB_NAME.
-- ============================================================

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS empresas (
    id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nombre        VARCHAR(120) NOT NULL,
    slug          VARCHAR(60)  NOT NULL,
    rfc           VARCHAR(20)  NULL,
    correo        VARCHAR(160) NULL,
    telefono      VARCHAR(40)  NULL,
    direccion     VARCHAR(220) NULL,
    activa        TINYINT(1)   NOT NULL DEFAULT 1,
    creada_en     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_empresas_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS licencias (
    id               INT UNSIGNED NOT NULL AUTO_INCREMENT,
    empresa_id       INT UNSIGNED NOT NULL,
    clave            VARCHAR(40)  NOT NULL,
    plan             ENUM('basico','profesional','empresarial') NOT NULL DEFAULT 'basico',
    estado           ENUM('activa','prueba','suspendida','vencida') NOT NULL DEFAULT 'prueba',
    max_usuarios     INT UNSIGNED NOT NULL DEFAULT 3,
    max_productos    INT UNSIGNED NOT NULL DEFAULT 500,
    inicio           DATE NOT NULL,
    vence            DATE NOT NULL,
    notas            VARCHAR(255) NULL,
    actualizada_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    creada_en        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_licencias_empresa (empresa_id),
    UNIQUE KEY uq_licencias_clave (clave),
    KEY idx_licencias_vence (vence),
    CONSTRAINT fk_licencias_empresa FOREIGN KEY (empresa_id)
        REFERENCES empresas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS usuarios (
    id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    empresa_id     INT UNSIGNED NULL,
    nombre         VARCHAR(120) NOT NULL,
    email          VARCHAR(160) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    rol            ENUM('superadmin','admin','operador') NOT NULL DEFAULT 'operador',
    activo         TINYINT(1) NOT NULL DEFAULT 1,
    ultimo_acceso  DATETIME NULL,
    creado_en      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_usuarios_email (email),
    KEY idx_usuarios_empresa (empresa_id, activo),
    CONSTRAINT fk_usuarios_empresa FOREIGN KEY (empresa_id)
        REFERENCES empresas (id) ON DELETE CASCADE,
    CONSTRAINT chk_usuarios_empresa CHECK (rol = 'superadmin' OR empresa_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS categorias (
    id           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    empresa_id   INT UNSIGNED NOT NULL,
    nombre       VARCHAR(80)  NOT NULL,
    descripcion  VARCHAR(200) NULL,
    activo       TINYINT(1)   NOT NULL DEFAULT 1,
    creada_en    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categorias_empresa_nombre (empresa_id, nombre),
    CONSTRAINT fk_categorias_empresa FOREIGN KEY (empresa_id)
        REFERENCES empresas (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS productos (
    id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    empresa_id     INT UNSIGNED NOT NULL,
    categoria_id   INT UNSIGNED NULL,
    sku            VARCHAR(40)  NOT NULL,
    nombre         VARCHAR(140) NOT NULL,
    descripcion    VARCHAR(300) NULL,
    unidad         VARCHAR(20)  NOT NULL DEFAULT 'pza',
    ubicacion      VARCHAR(60)  NULL,
    precio_compra  DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    precio_venta   DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    stock          INT NOT NULL DEFAULT 0,
    stock_minimo   INT NOT NULL DEFAULT 0,
    activo         TINYINT(1) NOT NULL DEFAULT 1,
    creado_en      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_productos_empresa_sku (empresa_id, sku),
    KEY idx_productos_empresa_activo (empresa_id, activo),
    KEY idx_productos_categoria (categoria_id),
    KEY idx_productos_stock (empresa_id, stock),
    CONSTRAINT fk_productos_empresa FOREIGN KEY (empresa_id)
        REFERENCES empresas (id) ON DELETE CASCADE,
    CONSTRAINT fk_productos_categoria FOREIGN KEY (categoria_id)
        REFERENCES categorias (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS movimientos (
    id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    empresa_id        INT UNSIGNED NOT NULL,
    producto_id       INT UNSIGNED NOT NULL,
    usuario_id        INT UNSIGNED NULL,
    tipo              ENUM('entrada','salida','ajuste') NOT NULL,
    cantidad          INT NOT NULL,
    stock_anterior    INT NOT NULL,
    stock_resultante  INT NOT NULL,
    motivo            VARCHAR(200) NULL,
    referencia        VARCHAR(80)  NULL,
    creado_en         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_mov_empresa_fecha (empresa_id, creado_en),
    KEY idx_mov_producto (producto_id),
    KEY idx_mov_usuario (usuario_id),
    CONSTRAINT fk_mov_empresa FOREIGN KEY (empresa_id)
        REFERENCES empresas (id) ON DELETE CASCADE,
    CONSTRAINT fk_mov_producto FOREIGN KEY (producto_id)
        REFERENCES productos (id) ON DELETE RESTRICT,
    CONSTRAINT fk_mov_usuario FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
