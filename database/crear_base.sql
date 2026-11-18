-- ============================================================
--  PiedPiper Inventario · creación de base de datos y usuario
--  Ejecutar UNA SOLA VEZ como root:
--    - phpMyAdmin → pestaña SQL → pegar y continuar
--    - o en terminal:  sudo mariadb < database/crear_base.sql
--
--  Es idempotente: no borra datos si la base ya existe.
-- ============================================================

CREATE DATABASE IF NOT EXISTS piedpiper_erp
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- El usuario se crea para conexión local (socket y TCP).
CREATE USER IF NOT EXISTS 'piedpiper'@'localhost' IDENTIFIED BY 'PiedPiper2026!';
CREATE USER IF NOT EXISTS 'piedpiper'@'127.0.0.1' IDENTIFIED BY 'PiedPiper2026!';

-- Si el usuario ya existía con otra contraseña, se alinea con el .env.
ALTER USER 'piedpiper'@'localhost' IDENTIFIED BY 'PiedPiper2026!';
ALTER USER 'piedpiper'@'127.0.0.1' IDENTIFIED BY 'PiedPiper2026!';

-- Permisos completos solo sobre la base de la aplicación.
GRANT ALL PRIVILEGES ON piedpiper_erp.* TO 'piedpiper'@'localhost';
GRANT ALL PRIVILEGES ON piedpiper_erp.* TO 'piedpiper'@'127.0.0.1';
FLUSH PRIVILEGES;
