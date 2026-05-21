import django
from django.conf import settings


def pytest_configure(config):
    """Fuerza SQLite en memoria antes de que Django se conecte a MySQL."""
    settings.DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }


import pytest
from django.contrib.auth.hashers import make_password
from usuarios.models import Usuario, PerfilProfesional, ReporteAdmin


@pytest.fixture
def usuario_cliente(db):
    u = Usuario(
        nombre="Ana", apellido="García",
        correo="ana.garcia@example.com",
        telefono="3001234567", direccion="Calle 10 # 20-30",
        tipo_usuario="cliente", estado_cuenta="aprobado", activo=True,
    )
    u.set_password("Clave$egura123")
    u.save()
    return u


@pytest.fixture
def usuario_profesional(db):
    u = Usuario(
        nombre="Carlos", apellido="López",
        correo="carlos.lopez@example.com",
        telefono="3109876543", direccion="Carrera 5 # 15-20",
        tipo_usuario="profesional", estado_cuenta="aprobado", activo=True,
    )
    u.set_password("Clave$egura456")
    u.save()
    return u


@pytest.fixture
def usuario_admin(db):
    u = Usuario(
        nombre="Admin", apellido="Sistema",
        correo="admin@homeplus.com",
        telefono="3200000000", direccion="Oficina Central",
        tipo_usuario="admin", estado_cuenta="aprobado", activo=True,
    )
    u.set_password("Admin$ecure789")
    u.save()
    return u


@pytest.fixture
def usuario_inactivo(db):
    u = Usuario(
        nombre="Pedro", apellido="Inactivo",
        correo="pedro.inactivo@example.com",
        telefono="3111111111", direccion="Calle 99",
        tipo_usuario="cliente", estado_cuenta="pendiente", activo=False,
    )
    u.set_password("Temporal123")
    u.save()
    return u


@pytest.fixture
def perfil_profesional(db, usuario_profesional):
    return PerfilProfesional.objects.create(
        usuario=usuario_profesional,
        servicio="electricidad",
        servicio_descripcion="Instalaciones eléctricas residenciales.",
        anos_experiencia=5,
        historial="3 años en empresa eléctrica, 2 independiente.",
        certificaciones="RETIE 2022",
    )