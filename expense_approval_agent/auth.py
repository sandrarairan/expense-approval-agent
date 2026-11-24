"""
Módulo de autenticación multi-usuario con SQLite + JWT (HS256).

- Los usuarios se guardan en la tabla `users` de `expenses_app.db` con contraseñas
  hasheadas mediante `scrypt` + salt aleatorio.
- El login/registro emite un JWT estándar firmado con `JWT_SECRET`.
- La validación siempre ocurre ANTES de invocar al agente/LLM.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from typing import Any, Dict, Optional

from .config import APP_DB_PATH, ROLE_DEFAULT_LIMITS, UMBRAL_APROBACION_AUTO

JWT_SECRET = os.getenv("JWT_SECRET", "dev-insecure-jwt-secret-change-in-prod")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_HOURS", "24")) * 3600

# Tokens estáticos legacy para scripts locales como `run_with_persistence.py`
AUTH_TOKENS_DB: Dict[str, Dict[str, Any]] = {
    "tok_ana_empleado": {
        "user_id": "ana@empresa.com",
        "nombre": "Ana Gómez",
        "rol": "empleado",
        "limite_aprobacion": 1000.0,
    },
    "tok_carlos_gerente": {
        "user_id": "carlos@empresa.com",
        "nombre": "Carlos Ruiz",
        "rol": "gerente",
        "limite_aprobacion": 5000.0,
    },
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def hash_password(password: str) -> str:
    """Genera un hash seguro con scrypt y salt aleatorio."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica la contraseña contra el hash almacenado en tiempo constante."""
    try:
        scheme, salt_hex, hash_hex = stored_hash.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def create_access_token(user: Dict[str, Any]) -> str:
    """Emite un JWT (HS256) firmado para el usuario autenticado."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user["user_id"],
        "nombre": user["nombre"],
        "rol": user["rol"],
        "limite_aprobacion": float(user["limite_aprobacion"]),
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> Dict[str, Any]:
    """Verifica la firma y expiración de un JWT HS256."""
    parts = token.split(".")
    if len(parts) != 3:
        raise PermissionError("Token JWT con formato inválido.")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_sig = _b64url_decode(sig_b64)
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise PermissionError("Token JWT corrupto o ilegible.") from exc

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise PermissionError("Firma del token JWT inválida.")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise PermissionError("El token JWT ha expirado. Inicia sesión nuevamente.")
    return payload


def _row_to_user(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "user_id": row["email"],
        "nombre": row["nombre"],
        "rol": row["rol"],
        "limite_aprobacion": float(row["limite_aprobacion"]),
    }


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    normalized = email.strip().lower()
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT email, nombre, rol, limite_aprobacion FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
        return _row_to_user(row) if row else None


def register_user(
    email: str,
    password: str,
    nombre: str,
    rol: str = "empleado",
    limite_aprobacion: Optional[float] = None,
) -> Dict[str, Any]:
    """Crea un nuevo usuario en SQLite y devuelve su perfil público."""
    normalized_email = email.strip().lower()
    clean_name = nombre.strip()
    clean_role = rol.strip().lower()
    if "@" not in normalized_email or len(normalized_email) < 5:
        raise ValueError("Ingresa un correo electrónico válido.")
    if len(clean_name) < 2:
        raise ValueError("Ingresa un nombre válido (mínimo 2 caracteres).")
    if len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    if clean_role not in ROLE_DEFAULT_LIMITS:
        raise ValueError(f"Rol inválido. Usa uno de: {sorted(ROLE_DEFAULT_LIMITS.keys())}.")

    limit_value = (
        float(limite_aprobacion)
        if limite_aprobacion is not None
        else ROLE_DEFAULT_LIMITS.get(clean_role, UMBRAL_APROBACION_AUTO)
    )
    pw_hash = hash_password(password)

    try:
        with sqlite3.connect(APP_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO users (email, nombre, rol, limite_aprobacion, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_email, clean_name, clean_role, limit_value, pw_hash),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError("Ya existe una cuenta registrada con ese correo.") from exc

    return {
        "user_id": normalized_email,
        "nombre": clean_name,
        "rol": clean_role,
        "limite_aprobacion": limit_value,
    }


def login_user(email: str, password: str) -> Dict[str, Any]:
    """Autentica correo y contraseña contra SQLite y devuelve el perfil público."""
    normalized = email.strip().lower()
    with sqlite3.connect(APP_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT email, nombre, rol, limite_aprobacion, password_hash FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise PermissionError("Correo o contraseña incorrectos.")
    return _row_to_user(row)


def seed_demo_users() -> None:
    """Crea usuarios iniciales de ejemplo si aún no existen en SQLite."""
    demo_accounts = [
        ("ana@empresa.com", "demo1234", "Ana Gómez", "empleado", 1000.0),
        ("carlos@empresa.com", "demo1234", "Carlos Ruiz", "gerente", 5000.0),
    ]
    for email, password, nombre, rol, limite in demo_accounts:
        if not get_user_by_email(email):
            register_user(email, password, nombre, rol, limite)


def extract_bearer_token(authorization: Optional[str]) -> str:
    """Extrae el token de un header `Authorization: Bearer <token>`."""
    if not authorization:
        raise PermissionError("Falta el header Authorization.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise PermissionError("Formato inválido. Usa: Authorization: Bearer <token>.")
    return token.strip()


def authenticate_token(token: str) -> Dict[str, Any]:
    """
    Valida un JWT firmado (o token legacy de desarrollo) y devuelve la identidad
    verificada del usuario desde SQLite.
    """
    if token in AUTH_TOKENS_DB:
        return AUTH_TOKENS_DB[token]

    payload = decode_access_token(token)
    email = str(payload.get("sub", ""))
    user = get_user_by_email(email)
    if not user:
        raise PermissionError("El usuario del token ya no existe.")
    return user


# Asegura que los usuarios demo existan al cargar el módulo
seed_demo_users()
