import os
from datetime import datetime
from typing import Optional, List

import bcrypt
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, func, desc
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from database import get_db, init_db, SessionLocal
from models import (
    Usuario,
    Cliente,
    OrdenTrabajo,
    Evidencia,
    TIPOS_SERVICIO,
    ESTADOS_OT,
    TIPOS_EVIDENCIA,
)

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

app = FastAPI(title="Superior Group Portal")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=60 * 60 * 24 * 7)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def _startup():
    init_db()
    _ensure_admin()


def _ensure_admin():
    email = os.getenv("ADMIN_EMAIL", "").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "")
    nombre = os.getenv("ADMIN_NOMBRE", "Administrador")
    if not email or not password:
        return
    db = SessionLocal()
    try:
        existe = db.query(Usuario).filter(Usuario.email == email).first()
        if existe:
            return
        db.add(
            Usuario(
                nombre=nombre,
                email=email,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                rol="admin",
                activo=True,
            )
        )
        db.commit()
        print(f"[startup] Admin inicial creado: {email}")
    finally:
        db.close()


# ---------- helpers ----------

def flash(request: Request, mensaje: str, tipo: str = "success"):
    mensajes = request.session.get("_flash", [])
    mensajes.append({"mensaje": mensaje, "tipo": tipo})
    request.session["_flash"] = mensajes


def get_flash(request: Request):
    mensajes = request.session.get("_flash", [])
    request.session["_flash"] = []
    return mensajes


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def current_user(request: Request, db: Session) -> Optional[Usuario]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(Usuario).filter(Usuario.id == user_id, Usuario.activo == True).first()  # noqa: E712


def require_user(request: Request, db: Session) -> Usuario:
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user


def require_admin(request: Request, db: Session) -> Usuario:
    user = require_user(request, db)
    if user.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    return user


def render(request: Request, db: Session, template: str, **ctx):
    user = current_user(request, db)
    base_ctx = {
        "user": user,
        "flashes": get_flash(request),
        "tipos_servicio": TIPOS_SERVICIO,
        "estados_ot": ESTADOS_OT,
        "tipos_evidencia": TIPOS_EVIDENCIA,
    }
    base_ctx.update(ctx)
    return templates.TemplateResponse(request, template, base_ctx)


def generar_numero_ot(db: Session) -> str:
    year = datetime.utcnow().year
    prefijo = f"OT-{year}-"
    ultima = (
        db.query(OrdenTrabajo)
        .filter(OrdenTrabajo.numero.like(f"{prefijo}%"))
        .order_by(desc(OrdenTrabajo.id))
        .first()
    )
    if ultima:
        try:
            correlativo = int(ultima.numero.split("-")[-1]) + 1
        except ValueError:
            correlativo = 1
    else:
        correlativo = 1
    return f"{prefijo}{correlativo:04d}"


def parse_fecha(valor: Optional[str]) -> Optional[datetime]:
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(valor, "%Y-%m-%dT%H:%M")
        except ValueError:
            return None


# ---------- AUTH ----------

@app.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/dashboard", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"flashes": get_flash(request)},
    )


@app.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(Usuario).filter(Usuario.email == email.lower().strip()).first()
    if not user or not user.activo or not verify_password(password, user.password_hash):
        flash(request, "Credenciales inválidas.", "error")
        return RedirectResponse("/login", status_code=302)
    request.session["user_id"] = user.id
    flash(request, f"Bienvenido, {user.nombre}.", "success")
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


# ---------- DASHBOARD ----------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    total_clientes = db.query(func.count(Cliente.id)).filter(Cliente.activo == True).scalar() or 0  # noqa: E712
    total_ot = db.query(func.count(OrdenTrabajo.id)).scalar() or 0
    por_estado = {
        estado: db.query(func.count(OrdenTrabajo.id)).filter(OrdenTrabajo.estado == estado).scalar() or 0
        for estado in ESTADOS_OT
    }
    recientes = (
        db.query(OrdenTrabajo)
        .order_by(desc(OrdenTrabajo.fecha_creacion))
        .limit(8)
        .all()
    )
    return render(
        request,
        db,
        "dashboard.html",
        total_clientes=total_clientes,
        total_ot=total_ot,
        por_estado=por_estado,
        recientes=recientes,
    )


# ---------- CLIENTES ----------

@app.get("/clientes", response_class=HTMLResponse)
def clientes_list(request: Request, q: Optional[str] = None, db: Session = Depends(get_db)):
    if not current_user(request, db):
        return RedirectResponse("/login", status_code=302)

    query = db.query(Cliente).filter(Cliente.activo == True)  # noqa: E712
    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                Cliente.nombre.ilike(term),
                Cliente.nit.ilike(term),
                Cliente.contacto.ilike(term),
                Cliente.ciudad.ilike(term),
            )
        )
    clientes = query.order_by(Cliente.nombre).all()
    return render(request, db, "clientes.html", clientes=clientes, q=q or "")


@app.post("/clientes/nuevo")
def clientes_nuevo(
    request: Request,
    nombre: str = Form(...),
    nit: Optional[str] = Form(None),
    contacto: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    telefono: Optional[str] = Form(None),
    ciudad: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user or user.rol != "admin":
        flash(request, "Solo administradores pueden crear clientes.", "error")
        return RedirectResponse("/clientes", status_code=302)

    cliente = Cliente(
        nombre=nombre.strip(),
        nit=(nit or "").strip() or None,
        contacto=(contacto or "").strip() or None,
        email=(email or "").strip() or None,
        telefono=(telefono or "").strip() or None,
        ciudad=(ciudad or "").strip() or None,
    )
    db.add(cliente)
    db.commit()
    flash(request, "Cliente creado.", "success")
    return RedirectResponse("/clientes", status_code=302)


@app.post("/clientes/{cliente_id}/eliminar")
def clientes_eliminar(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.rol != "admin":
        flash(request, "Solo administradores pueden eliminar clientes.", "error")
        return RedirectResponse("/clientes", status_code=302)

    cliente = db.query(Cliente).get(cliente_id)
    if cliente:
        cliente.activo = False
        db.commit()
        flash(request, "Cliente eliminado.", "success")
    return RedirectResponse("/clientes", status_code=302)


# ---------- ÓRDENES ----------

@app.get("/ordenes", response_class=HTMLResponse)
def ordenes_list(
    request: Request,
    cliente_id: Optional[int] = None,
    estado: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if not current_user(request, db):
        return RedirectResponse("/login", status_code=302)

    query = db.query(OrdenTrabajo)
    if cliente_id:
        query = query.filter(OrdenTrabajo.cliente_id == cliente_id)
    if estado:
        query = query.filter(OrdenTrabajo.estado == estado)
    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                OrdenTrabajo.numero.ilike(term),
                OrdenTrabajo.tipo_servicio.ilike(term),
                OrdenTrabajo.sede.ilike(term),
                OrdenTrabajo.descripcion.ilike(term),
            )
        )
    ordenes = query.order_by(desc(OrdenTrabajo.fecha_creacion)).all()
    clientes = db.query(Cliente).filter(Cliente.activo == True).order_by(Cliente.nombre).all()  # noqa: E712
    tecnicos = db.query(Usuario).filter(Usuario.activo == True).order_by(Usuario.nombre).all()  # noqa: E712
    return render(
        request,
        db,
        "ordenes.html",
        ordenes=ordenes,
        clientes=clientes,
        tecnicos=tecnicos,
        filtro_cliente=cliente_id,
        filtro_estado=estado or "",
        q=q or "",
    )


@app.post("/ordenes/nueva")
def ordenes_nueva(
    request: Request,
    cliente_id: int = Form(...),
    tipo_servicio: str = Form(...),
    sede: Optional[str] = Form(None),
    fecha_programada: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    tecnico_id: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    tecnico_int: Optional[int] = None
    if tecnico_id and tecnico_id.strip():
        try:
            tecnico_int = int(tecnico_id)
        except ValueError:
            tecnico_int = None

    orden = OrdenTrabajo(
        numero=generar_numero_ot(db),
        cliente_id=cliente_id,
        tecnico_id=tecnico_int,
        tipo_servicio=tipo_servicio,
        sede=(sede or "").strip() or None,
        fecha_programada=parse_fecha(fecha_programada),
        descripcion=(descripcion or "").strip() or None,
        notas=(notas or "").strip() or None,
        estado="pendiente",
    )
    db.add(orden)
    db.commit()
    db.refresh(orden)
    flash(request, f"Orden {orden.numero} creada.", "success")
    return RedirectResponse(f"/ordenes/{orden.id}", status_code=302)


@app.get("/ordenes/{orden_id}", response_class=HTMLResponse)
def orden_detalle(orden_id: int, request: Request, db: Session = Depends(get_db)):
    if not current_user(request, db):
        return RedirectResponse("/login", status_code=302)

    orden = db.query(OrdenTrabajo).get(orden_id)
    if not orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    evidencias_por_tipo = {tipo: [] for tipo in TIPOS_EVIDENCIA}
    for ev in orden.evidencias:
        evidencias_por_tipo.setdefault(ev.tipo, []).append(ev)

    clientes = db.query(Cliente).filter(Cliente.activo == True).order_by(Cliente.nombre).all()  # noqa: E712
    tecnicos = db.query(Usuario).filter(Usuario.activo == True).order_by(Usuario.nombre).all()  # noqa: E712

    return render(
        request,
        db,
        "orden_detalle.html",
        orden=orden,
        evidencias_por_tipo=evidencias_por_tipo,
        clientes=clientes,
        tecnicos=tecnicos,
    )


@app.post("/ordenes/{orden_id}/editar")
def orden_editar(
    orden_id: int,
    request: Request,
    cliente_id: int = Form(...),
    tipo_servicio: str = Form(...),
    estado: str = Form(...),
    sede: Optional[str] = Form(None),
    fecha_programada: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    tecnico_id: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    orden = db.query(OrdenTrabajo).get(orden_id)
    if not orden:
        raise HTTPException(status_code=404)

    tecnico_int: Optional[int] = None
    if tecnico_id and tecnico_id.strip():
        try:
            tecnico_int = int(tecnico_id)
        except ValueError:
            tecnico_int = None

    orden.cliente_id = cliente_id
    orden.tipo_servicio = tipo_servicio
    orden.estado = estado if estado in ESTADOS_OT else orden.estado
    orden.sede = (sede or "").strip() or None
    orden.fecha_programada = parse_fecha(fecha_programada)
    orden.descripcion = (descripcion or "").strip() or None
    orden.tecnico_id = tecnico_int
    orden.notas = (notas or "").strip() or None
    db.commit()
    flash(request, "Orden actualizada.", "success")
    return RedirectResponse(f"/ordenes/{orden_id}", status_code=302)


@app.post("/ordenes/{orden_id}/eliminar")
def orden_eliminar(orden_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.rol != "admin":
        flash(request, "Solo administradores pueden eliminar órdenes.", "error")
        return RedirectResponse(f"/ordenes/{orden_id}", status_code=302)

    orden = db.query(OrdenTrabajo).get(orden_id)
    if not orden:
        return RedirectResponse("/ordenes", status_code=302)

    for ev in list(orden.evidencias):
        try:
            cloudinary.uploader.destroy(ev.public_id)
        except Exception:
            pass

    db.delete(orden)
    db.commit()
    flash(request, "Orden eliminada.", "success")
    return RedirectResponse("/ordenes", status_code=302)


# ---------- EVIDENCIAS ----------

@app.post("/ordenes/{orden_id}/evidencias/subir")
async def evidencias_subir(
    orden_id: int,
    request: Request,
    tipo: str = Form(...),
    descripcion: Optional[str] = Form(None),
    archivos: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    orden = db.query(OrdenTrabajo).get(orden_id)
    if not orden:
        raise HTTPException(status_code=404)

    if tipo not in TIPOS_EVIDENCIA:
        flash(request, "Tipo de evidencia inválido.", "error")
        return RedirectResponse(f"/ordenes/{orden_id}", status_code=302)

    carpeta = f"superior_group/OT-{orden.id}/{tipo}"
    subidas = 0
    for archivo in archivos:
        if not archivo or not archivo.filename:
            continue
        try:
            data = await archivo.read()
            if not data:
                continue
            resultado = cloudinary.uploader.upload(
                data,
                folder=carpeta,
                resource_type="image",
            )
            evidencia = Evidencia(
                orden_id=orden.id,
                subido_por_id=user.id,
                tipo=tipo,
                url=resultado.get("secure_url"),
                public_id=resultado.get("public_id"),
                descripcion=(descripcion or "").strip() or None,
            )
            db.add(evidencia)
            subidas += 1
        except Exception as exc:
            flash(request, f"Error al subir {archivo.filename}: {exc}", "error")

    if subidas:
        db.commit()
        flash(request, f"{subidas} foto(s) subidas.", "success")
    return RedirectResponse(f"/ordenes/{orden_id}", status_code=302)


@app.post("/evidencias/{evidencia_id}/eliminar")
def evidencia_eliminar(evidencia_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)

    ev = db.query(Evidencia).get(evidencia_id)
    if not ev:
        return RedirectResponse("/ordenes", status_code=302)

    orden_id = ev.orden_id
    try:
        cloudinary.uploader.destroy(ev.public_id)
    except Exception:
        pass
    db.delete(ev)
    db.commit()
    flash(request, "Evidencia eliminada.", "success")
    return RedirectResponse(f"/ordenes/{orden_id}", status_code=302)


# ---------- USUARIOS ----------

@app.get("/usuarios", response_class=HTMLResponse)
def usuarios_list(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.rol != "admin":
        flash(request, "Solo administradores.", "error")
        return RedirectResponse("/dashboard", status_code=302)

    usuarios = db.query(Usuario).order_by(Usuario.nombre).all()
    return render(request, db, "usuarios.html", usuarios=usuarios)


@app.post("/usuarios/nuevo")
def usuarios_nuevo(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    rol: str = Form("tecnico"),
    db: Session = Depends(get_db),
):
    user = current_user(request, db)
    if not user or user.rol != "admin":
        flash(request, "Solo administradores.", "error")
        return RedirectResponse("/usuarios", status_code=302)

    email_clean = email.lower().strip()
    existe = db.query(Usuario).filter(Usuario.email == email_clean).first()
    if existe:
        flash(request, "Ese email ya está registrado.", "error")
        return RedirectResponse("/usuarios", status_code=302)

    nuevo = Usuario(
        nombre=nombre.strip(),
        email=email_clean,
        password_hash=hash_password(password),
        rol=rol if rol in ("admin", "tecnico") else "tecnico",
        activo=True,
    )
    db.add(nuevo)
    db.commit()
    flash(request, "Usuario creado.", "success")
    return RedirectResponse("/usuarios", status_code=302)


@app.post("/usuarios/{usuario_id}/eliminar")
def usuarios_eliminar(usuario_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user or user.rol != "admin":
        flash(request, "Solo administradores.", "error")
        return RedirectResponse("/usuarios", status_code=302)
    if user.id == usuario_id:
        flash(request, "No puedes eliminarte a ti mismo.", "error")
        return RedirectResponse("/usuarios", status_code=302)

    obj = db.query(Usuario).get(usuario_id)
    if obj:
        obj.activo = False
        db.commit()
        flash(request, "Usuario desactivado.", "success")
    return RedirectResponse("/usuarios", status_code=302)
