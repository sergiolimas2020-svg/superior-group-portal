from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

TIPOS_SERVICIO = [
    "Pintura",
    "Plomería",
    "Electricidad",
    "Drywall",
    "Impermeabilización",
    "Pisos y Enchapes",
    "Carpintería",
    "Mantenimiento General",
    "Obra Civil",
    "Limpieza Especializada",
    "Otro",
]

ESTADOS_OT = ["pendiente", "en_proceso", "completada", "facturada"]
TIPOS_EVIDENCIA = ["antes", "durante", "despues"]


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), default="tecnico", nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)

    ordenes = relationship("OrdenTrabajo", back_populates="tecnico", foreign_keys="OrdenTrabajo.tecnico_id")
    evidencias = relationship("Evidencia", back_populates="subido_por")


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(150), nullable=False)
    nit = Column(String(40), nullable=True)
    contacto = Column(String(120), nullable=True)
    email = Column(String(120), nullable=True)
    telefono = Column(String(40), nullable=True)
    ciudad = Column(String(80), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)

    ordenes = relationship("OrdenTrabajo", back_populates="cliente")


class OrdenTrabajo(Base):
    __tablename__ = "ordenes_trabajo"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(30), unique=True, nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    tecnico_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tipo_servicio = Column(String(80), nullable=False)
    descripcion = Column(Text, nullable=True)
    sede = Column(String(150), nullable=True)
    estado = Column(String(20), default="pendiente", nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_programada = Column(DateTime, nullable=True)
    notas = Column(Text, nullable=True)

    cliente = relationship("Cliente", back_populates="ordenes")
    tecnico = relationship("Usuario", back_populates="ordenes", foreign_keys=[tecnico_id])
    evidencias = relationship("Evidencia", back_populates="orden", cascade="all, delete-orphan")


class Evidencia(Base):
    __tablename__ = "evidencias"

    id = Column(Integer, primary_key=True, index=True)
    orden_id = Column(Integer, ForeignKey("ordenes_trabajo.id"), nullable=False)
    subido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tipo = Column(String(20), nullable=False)
    url = Column(String(500), nullable=False)
    public_id = Column(String(255), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_subida = Column(DateTime, default=datetime.utcnow, nullable=False)

    orden = relationship("OrdenTrabajo", back_populates="evidencias")
    subido_por = relationship("Usuario", back_populates="evidencias")
