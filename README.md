# PiedPiper Inventario

Sistema de gestión de inventario multiempresa construido con **Flask + MariaDB**.
Incluye autenticación, roles, aislamiento de datos por empresa, licencias y una
consola administrativa con tema oscuro/claro.

![PiedPiper](static/img/flautista.jpg)

---

## Características

- **Multiempresa (multi-tenant):** cada empresa ve únicamente sus productos,
  categorías, movimientos y usuarios.
- **Roles:** `superadmin` (plataforma), `admin` (empresa) y `operador`.
- **Inventario:** productos, categorías, stock mínimo, precios, alertas.
- **Movimientos auditables:** entradas, salidas y ajustes con actualización
  atómica del stock (`SELECT ... FOR UPDATE`). No se editan ni eliminan.
- **Licencias:** planes Básico, Profesional y Empresarial; límites de usuarios y
  productos; bloqueo automático por vencimiento o suspensión.
- **Seguridad:** contraseñas con hash Werkzeug, CSRF en formularios, consultas
  parametrizadas, sesiones firmadas y control de acceso por rol.
- **Interfaz:** dashboard con KPIs, gráfica de flujo, tablas ordenables, filtros,
  paginación, tema oscuro/claro persistente y diseño adaptable.

---

## Requisitos

- Python 3.9 o superior
- MariaDB 10.5+ (o MySQL 8 compatible)

---

## Instalación rápida

```bash
cd piedpiper-erp
bash setup.sh
```

El script crea `.venv`, instala dependencias y genera `.env` si no existe.

### 1. Preparar MariaDB

Crea la base y el usuario con el script incluido (solo la primera vez):

```bash
sudo mariadb < database/crear_base.sql
```

O pega el contenido de `database/crear_base.sql` en **phpMyAdmin → SQL**.
El script es idempotente: se puede ejecutar de nuevo sin borrar datos.

### 2. Configurar `.env`

```dotenv
SECRET_KEY=una-clave-larga-y-aleatoria
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=piedpiper
DB_PASSWORD=PiedPiper2026!
DB_NAME=piedpiper_erp
DEMO_MODE=true
```

### 3. Cargar esquema y datos demo

```bash
source .venv/bin/activate
python seed.py
```

Para reiniciar desde cero:

```bash
python seed.py --fresh --yes
```

Solo esquema, sin datos demo:

```bash
python seed.py --no-demo
```

### 4. Arrancar

```bash
bash run.sh
# http://127.0.0.1:5000
```

`run.sh` comprueba la conexión a MariaDB antes de arrancar y, si el servicio
está apagado, intenta iniciarlo.

---

## Servidor MariaDB y phpMyAdmin

MariaDB queda **habilitado al arranque del sistema** y guarda los datos en
`/var/lib/mysql`, así que sobreviven reinicios y apagones.

```bash
bash db.sh estado      # ¿está activo y responde la base?
bash db.sh iniciar     # arrancar el servidor
bash db.sh detener     # apagarlo (los datos se conservan)
bash db.sh reiniciar   # reiniciarlo
bash db.sh habilitar   # arrancar siempre con el sistema
bash db.sh verificar   # probar la conexión del .env
bash db.sh seed        # aplicar esquema + datos demo
bash db.sh reset       # borrar y recrear la base (pide confirmación)
```

También puedes usar `systemctl` directamente:

```bash
sudo systemctl start mariadb
sudo systemctl stop mariadb
sudo systemctl status mariadb
sudo systemctl enable mariadb   # arranque automático
```

### Administrar desde phpMyAdmin

Abre <http://127.0.0.1/phpmyadmin/> e inicia sesión como `root`
(o como `piedpiper` con la contraseña del `.env`).

- Base de datos: `piedpiper_erp`
- Tablas: `empresas`, `licencias`, `usuarios`, `categorias`, `productos`, `movimientos`
- Los cambios hechos en phpMyAdmin se reflejan al instante en la aplicación.

> El usuario `piedpiper` solo tiene permisos sobre `piedpiper_erp.*`, que es
> justo lo que necesita la aplicación. Usa `root` para tareas del servidor.

### Respaldo rápido

```bash
mariadb-dump -u piedpiper -p'PiedPiper2026!' piedpiper_erp > respaldo_$(date +%F).sql
```

Restaurar:

```bash
mariadb -u piedpiper -p'PiedPiper2026!' piedpiper_erp < respaldo_2026-01-01.sql
```

Alternativa con Flask CLI:

```bash
flask --app app run --debug
```

---

## Credenciales de demostración

| Rol | Correo | Contraseña |
| --- | --- | --- |
| Superadministrador | `admin@piedpiper.software` | `PiedPiper2026!` |
| Administrador de empresa | `admin@demo.mx` | `Demo2026!` |
| Operador | `operador@demo.mx` | `Operador2026!` |
| Administrador (2.ª empresa) | `admin@norte.mx` | `Norte2026!` |

> `DEMO_MODE=true` muestra estos accesos en el login. En producción usa
> `DEMO_MODE=false` y cambia todas las contraseñas.

---

## Estructura del proyecto

```
piedpiper-erp/
├── app.py                 # Fábrica de la aplicación, filtros y errores
├── config.py              # Configuración vía variables de entorno
├── db.py                  # Conexión PyMySQL y helpers de consulta
├── security.py            # Sesión, CSRF, roles y aislamiento por empresa
├── utils.py               # Validaciones, paginación y catálogo de planes
├── schema.sql             # DDL de MariaDB
├── seed.py                # Creación de base y datos de demostración
├── db.sh                  # Arranque/parada y respaldo de MariaDB
├── database/
│   └── crear_base.sql     # Base y usuario (ejecutar una vez como root)
├── blueprints/
│   ├── auth.py
│   ├── dashboard.py
│   ├── productos.py
│   ├── categorias.py
│   ├── movimientos.py
│   ├── usuarios.py
│   ├── empresas.py
│   └── licencias.py
├── templates/
│   ├── base.html
│   ├── auth_base.html
│   ├── auth/
│   ├── dashboard/
│   ├── productos/
│   ├── categorias/
│   ├── movimientos/
│   ├── usuarios/
│   ├── empresas/
│   ├── licencias/
│   ├── errors/
│   └── partials/
├── static/
│   ├── css/app.css
│   ├── js/app.js
│   └── img/
├── requirements.txt
├── .env.example
├── setup.sh
└── run.sh
```

---

## Modelo de datos

| Tabla | Propósito |
| --- | --- |
| `empresas` | Clientes de la plataforma; raíz del aislamiento. |
| `licencias` | Una por empresa: plan, vigencia, estado y límites. |
| `usuarios` | Cuentas con rol y empresa asignada. |
| `categorias` | Agrupación de productos por empresa. |
| `productos` | Catálogo con SKU único por empresa, stock y precios. |
| `movimientos` | Bitácora inmutable de entradas, salidas y ajustes. |

Todas las claves foráneas usan `ON DELETE CASCADE`/`RESTRICT` según la entidad.
Los índices cubren búsquedas por empresa, SKU, estado y fecha.

---

## Seguridad

- Contraseñas almacenadas con `generate_password_hash` (Werkzeug).
- Token CSRF por sesión validado en cada `POST`.
- Todas las consultas usan parámetros `%s` (sin interpolación de entrada).
- Límite de intentos de login por IP + correo (6 en 5 minutos).
- Cookies `HttpOnly` y `SameSite=Lax`; activa `COOKIE_SECURE=true` con HTTPS.
- El superadministrador puede entrar a una empresa para soporte, pero los
  usuarios locales quedan bloqueados si la licencia no está vigente.

---

## Licencias y planes

| Plan | Usuarios | Productos | Precio de referencia |
| --- | --- | --- | --- |
| Básico | 3 | 500 | $299 MXN / mes |
| Profesional | 10 | 2,000 | $699 MXN / mes |
| Empresarial | 50 | 20,000 | $1,490 MXN / mes |

Estados válidos: `activa`, `prueba`, `suspendida`, `vencida`.
Una licencia vencida, suspendida o una empresa inactiva restringe a sus usuarios
a las pantallas **Mi licencia** y **Mi cuenta** hasta regularizarse.

---

## Producción

1. `DEMO_MODE=false`, `COOKIE_SECURE=true` y un `SECRET_KEY` único.
2. Sirve la aplicación con un WSGI (Gunicorn/uWSGI) detrás de Nginx con HTTPS.
3. Crea un usuario MariaDB con permisos solo sobre `piedpiper_erp.*`.
4. Programa respaldos de la base y rota las contraseñas demo.

Ejemplo con Gunicorn:

```bash
python -m pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:8000 "app:app"
```

---

## Soporte

PiedPiper Software · `soporte@piedpiper.software`
