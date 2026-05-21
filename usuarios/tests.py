
 
import pytest
from django.db import IntegrityError
from django.contrib.auth.hashers import check_password
 
from usuarios.models import Usuario, PerfilProfesional, ReporteAdmin
 
 
# ===========================================================================
# MODELO: Usuario
# ===========================================================================
 
class TestUsuarioCreacion:
    """Validar que el modelo Usuario se crea correctamente."""
 
    def test_creacion_usuario_cliente(self, usuario_cliente):
        """Un usuario cliente debe persistir con los campos correctos."""
        # Assert
        assert usuario_cliente.pk is not None
        assert usuario_cliente.nombre == "Ana"
        assert usuario_cliente.apellido == "García"
        assert usuario_cliente.tipo_usuario == "cliente"
 
    def test_tipo_usuario_default_es_cliente(self, db):
        """El tipo de usuario por defecto debe ser 'cliente'."""
        # Arrange & Act
        u = Usuario(
            nombre="Test",
            apellido="Default",
            correo="default@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
        )
        # Assert — sin tocar tipo_usuario
        assert u.tipo_usuario == "cliente"
 
    def test_estado_cuenta_default_es_pendiente(self, db):
        """El estado de cuenta por defecto debe ser 'pendiente'."""
        u = Usuario(
            nombre="Test",
            apellido="Pendiente",
            correo="pendiente@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
        )
        assert u.estado_cuenta == "pendiente"
 
    def test_activo_default_es_false(self, db):
        """Un usuario nuevo debe tener activo=False por defecto."""
        u = Usuario(
            nombre="Test",
            apellido="Inactivo",
            correo="inactivo2@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
        )
        assert u.activo is False
 
    def test_correo_unico(self, db, usuario_cliente):
        """No deben existir dos usuarios con el mismo correo."""
        # Arrange
        duplicado = Usuario(
            nombre="Otra",
            apellido="Persona",
            correo=usuario_cliente.correo,  # correo ya existente
            telefono="311",
            direccion="Otra dir",
            password="x",
        )
        # Act & Assert
        with pytest.raises(IntegrityError):
            duplicado.save()
 
    def test_token_activacion_nulo_por_defecto(self, db):
        """El token de activación debe ser nulo al crear el usuario."""
        u = Usuario(
            nombre="Sin",
            apellido="Token",
            correo="sintoken@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
        )
        assert u.token_activacion is None
        assert u.token_recuperacion is None
 
 
class TestUsuarioDunderStr:
    """Validar el método __str__ del modelo Usuario."""
 
    def test_str_retorna_nombre_apellido_correo(self, usuario_cliente):
        """__str__ debe devolver 'Nombre Apellido (correo)'."""
        esperado = "Ana García (ana.garcia@example.com)"
        assert str(usuario_cliente) == esperado
 
 
class TestUsuarioSetPassword:
    """Validar el método set_password()."""
 
    def test_set_password_encripta_correctamente(self, db):
        """set_password debe almacenar el hash, no el texto plano."""
        # Arrange
        u = Usuario(
            nombre="Hash",
            apellido="Test",
            correo="hash@test.com",
            telefono="300",
            direccion="Calle 1",
        )
        raw = "MiClave123"
 
        # Act
        u.set_password(raw)
 
        # Assert
        assert u.password != raw
        assert check_password(raw, u.password)
 
    def test_set_password_no_almacena_texto_plano(self, db):
        """La contraseña guardada nunca debe ser igual al texto plano."""
        u = Usuario(
            nombre="Plain",
            apellido="Test",
            correo="plain@test.com",
            telefono="300",
            direccion="Calle 1",
        )
        raw = "TextoPlano"
        u.set_password(raw)
 
        assert raw not in u.password
 
 
class TestUsuarioGenerarToken:
    """Validar el método generar_token()."""
 
    def test_generar_token_retorna_string(self, usuario_cliente):
        """generar_token debe retornar un string."""
        token = usuario_cliente.generar_token()
        assert isinstance(token, str)
 
    def test_generar_token_longitud_32(self, usuario_cliente):
        """El token UUID4 sin guiones tiene 32 caracteres."""
        token = usuario_cliente.generar_token()
        assert len(token) == 32
 
    def test_generar_token_es_unico(self, usuario_cliente):
        """Dos llamadas seguidas deben producir tokens distintos."""
        token1 = usuario_cliente.generar_token()
        token2 = usuario_cliente.generar_token()
        assert token1 != token2
 
    def test_generar_token_sin_guiones(self, usuario_cliente):
        """El token no debe contener guiones (UUID normalizado)."""
        token = usuario_cliente.generar_token()
        assert "-" not in token
 
 
class TestUsuarioPuedeIniciarSesion:
    """Validar el método puede_iniciar_sesion()."""
 
    def test_usuario_activo_aprobado_puede_iniciar_sesion(self, usuario_cliente):
        """Un usuario activo y aprobado debe poder iniciar sesión."""
        assert usuario_cliente.puede_iniciar_sesion() is True
 
    def test_usuario_inactivo_no_puede_iniciar_sesion(self, usuario_inactivo):
        """Un usuario inactivo (activo=False) no debe poder iniciar sesión."""
        assert usuario_inactivo.puede_iniciar_sesion() is False
 
    def test_usuario_pendiente_no_puede_iniciar_sesion(self, db):
        """Un usuario con estado 'pendiente' no puede iniciar sesión aunque esté activo."""
        # Arrange
        u = Usuario(
            nombre="Pendiente",
            apellido="Activo",
            correo="pendiente.activo@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
            activo=True,
            estado_cuenta="pendiente",
        )
        # Act & Assert
        assert u.puede_iniciar_sesion() is False
 
    def test_usuario_rechazado_no_puede_iniciar_sesion(self, db):
        """Un usuario con estado 'rechazado' no puede iniciar sesión."""
        u = Usuario(
            nombre="Rechazado",
            apellido="Test",
            correo="rechazado@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
            activo=True,
            estado_cuenta="rechazado",
        )
        assert u.puede_iniciar_sesion() is False
 
    def test_ambas_condiciones_requeridas(self, db):
        """Debe requerir activo=True Y estado_cuenta='aprobado' simultáneamente."""
        # Sólo activo, sin aprobar → False
        u = Usuario(
            nombre="Solo",
            apellido="Activo",
            correo="solo.activo@test.com",
            telefono="300",
            direccion="Calle 1",
            password="x",
            activo=True,
            estado_cuenta="pendiente",
        )
        assert u.puede_iniciar_sesion() is False
 
 
# ===========================================================================
# MODELO: PerfilProfesional
# ===========================================================================
 
class TestPerfilProfesionalCreacion:
    """Validar la creación correcta del modelo PerfilProfesional."""
 
    def test_creacion_perfil_profesional(self, perfil_profesional):
        """El perfil debe persistir con los campos ingresados."""
        assert perfil_profesional.pk is not None
        assert perfil_profesional.servicio == "electricidad"
        assert perfil_profesional.anos_experiencia == 5
 
    def test_relacion_onetoone_con_usuario(self, perfil_profesional, usuario_profesional):
        """Debe existir una relación OneToOne entre PerfilProfesional y Usuario."""
        assert perfil_profesional.usuario == usuario_profesional
        assert usuario_profesional.perfil_profesional == perfil_profesional
 
    def test_no_permite_dos_perfiles_por_usuario(self, db, perfil_profesional, usuario_profesional):
        """Un usuario no puede tener dos perfiles profesionales (OneToOne)."""
        with pytest.raises(IntegrityError):
            PerfilProfesional.objects.create(
                usuario=usuario_profesional,
                servicio="plomeria",
                servicio_descripcion="Duplicado",
                anos_experiencia=1,
                historial="Duplicado",
            )
 
    def test_certificaciones_opcionales(self, db, usuario_profesional):
        """El campo certificaciones puede ser nulo."""
        perfil = PerfilProfesional.objects.create(
            usuario=usuario_profesional,
            servicio="pintura",
            servicio_descripcion="Pintura interior y exterior.",
            anos_experiencia=3,
            historial="3 años como pintor independiente.",
            certificaciones=None,
        )
        assert perfil.certificaciones is None
 
    def test_str_incluye_nombre_y_servicio(self, perfil_profesional):
        """__str__ debe incluir el nombre del usuario y el servicio."""
        resultado = str(perfil_profesional)
        assert "Carlos" in resultado
        assert "Electricidad" in resultado
 
 
# ===========================================================================
# MODELO: ReporteAdmin
# ===========================================================================
 
class TestReporteAdminCreacion:
    """Validar la creación y campos del modelo ReporteAdmin."""
 
    def test_creacion_reporte(self, db, usuario_admin):
        """Un reporte debe crearse correctamente con sus campos."""
        # Arrange & Act
        reporte = ReporteAdmin.objects.create(
            titulo="Reporte mensual de usuarios",
            tipo="usuarios",
            descripcion="Resumen de altas del mes.",
            creado_por=usuario_admin,
        )
        # Assert
        assert reporte.pk is not None
        assert reporte.titulo == "Reporte mensual de usuarios"
 
    def test_tipo_reporte_valido(self, db, usuario_admin):
        """El campo tipo debe aceptar los valores del CHOICES."""
        tipos_validos = ["usuarios", "profesionales", "pendientes", "general"]
        for tipo in tipos_validos:
            r = ReporteAdmin.objects.create(
                titulo=f"Reporte {tipo}",
                tipo=tipo,
                creado_por=usuario_admin,
            )
            assert r.tipo == tipo
 
    def test_descripcion_y_datos_json_opcionales(self, db, usuario_admin):
        """Descripcion y datos_json pueden estar vacíos."""
        reporte = ReporteAdmin.objects.create(
            titulo="Sin datos extra",
            tipo="general",
            creado_por=usuario_admin,
        )
        assert reporte.descripcion == ""
        assert reporte.datos_json == ""
 
    def test_creado_por_puede_ser_nulo_al_borrar_usuario(self, db, usuario_admin):
        """Al eliminar el admin, creado_por queda en NULL (SET_NULL)."""
        reporte = ReporteAdmin.objects.create(
            titulo="Reporte huérfano",
            tipo="general",
            creado_por=usuario_admin,
        )
        id_reporte = reporte.pk
        usuario_admin.delete()
 
        reporte.refresh_from_db()
        assert reporte.creado_por is None
 
    def test_str_reporte(self, db, usuario_admin):
        """__str__ debe mostrar título y tipo legible."""
        reporte = ReporteAdmin.objects.create(
            titulo="Control Profesionales",
            tipo="profesionales",
            creado_por=usuario_admin,
        )
        resultado = str(reporte)
        assert "Control Profesionales" in resultado
        assert "Reporte de profesionales" in resultado