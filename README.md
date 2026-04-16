# Superior Group Portal

Portal web para gestión de órdenes de trabajo y evidencias fotográficas de **Superior Group S.A.S** (arreglos locativos).

Construido con **FastAPI + SQLite + Jinja2 + Cloudinary**.

## Características

- Gestión de clientes, órdenes de trabajo y usuarios (admin / técnico).
- Numeración automática de OTs (`OT-2025-0001`).
- Estados de OT: pendiente, en proceso, completada, facturada.
- Evidencias fotográficas agrupadas por tipo (antes / durante / después), almacenadas en Cloudinary.
- Dashboard con métricas operacionales.
- Diseño oscuro industrial profesional.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2, SQLite, bcrypt
- **Frontend:** Jinja2 templates, CSS puro, JavaScript vanilla
- **Almacenamiento de imágenes:** Cloudinary
- **Auth:** Sesiones con `itsdangerous` via Starlette `SessionMiddleware`

## Instalación local

```bash
git clone https://github.com/natalygamboa11-a11y/superior-group-portal.git
cd superior-group-portal

python3 -m venv venv
source venv/bin/activate   # En Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edita .env y completa: SECRET_KEY, CLOUDINARY_*, ADMIN_*

python seed.py             # crea el primer usuario admin
uvicorn main:app --reload --port 8000
```

Abre http://localhost:8000 e inicia sesión con las credenciales definidas en `.env`.

## Variables de entorno

| Variable | Descripción |
|---|---|
| `SECRET_KEY` | Clave secreta para las sesiones |
| `CLOUDINARY_CLOUD_NAME` | Nombre de la cuenta Cloudinary |
| `CLOUDINARY_API_KEY` | API Key de Cloudinary |
| `CLOUDINARY_API_SECRET` | API Secret de Cloudinary |
| `DATABASE_URL` | URL de la base de datos (default: sqlite local) |
| `ADMIN_EMAIL` | Email del primer admin creado por `seed.py` |
| `ADMIN_PASSWORD` | Contraseña inicial del admin |
| `ADMIN_NOMBRE` | Nombre del admin |

## Estructura

```
superior-group-portal/
├── main.py             # Rutas FastAPI
├── models.py           # Modelos SQLAlchemy
├── database.py         # Engine y sesión DB
├── seed.py             # Crea usuario admin inicial
├── requirements.txt
├── Procfile            # Despliegue Heroku/Railway
├── templates/          # Jinja2 templates
└── static/
    ├── css/main.css
    └── js/app.js
```

## Despliegue

Incluye `Procfile` listo para **Heroku**, **Railway** o cualquier plataforma compatible.
Recuerda configurar las variables de entorno en el panel del proveedor antes de lanzar.

## Licencia

Uso interno — Superior Group S.A.S
