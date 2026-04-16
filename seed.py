import os
import bcrypt
from dotenv import load_dotenv

from database import SessionLocal, init_db
from models import Usuario

load_dotenv()


def main():
    init_db()
    email = os.getenv("ADMIN_EMAIL", "admin@superiorgroup.com.co").lower().strip()
    password = os.getenv("ADMIN_PASSWORD", "Admin2025*")
    nombre = os.getenv("ADMIN_NOMBRE", "Administrador")

    db = SessionLocal()
    try:
        existe = db.query(Usuario).filter(Usuario.email == email).first()
        if existe:
            print(f"[seed] Usuario admin ya existe: {email}")
            return
        hash_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            nombre=nombre,
            email=email,
            password_hash=hash_pw,
            rol="admin",
            activo=True,
        )
        db.add(admin)
        db.commit()
        print(f"[seed] Admin creado: {email} / {password}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
