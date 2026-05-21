
 
import pytest
from decimal import Decimal
from django.db import IntegrityError
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
 
from servicios.models import Servicio, Aplicacion, Evidencia, Calificacion, VisitaDiagnostico
from usuarios.models import Usuario
 
 
# ---------------------------------------------------------------------------
# Fixtures locales de la app servicios
# ---------------------------------------------------------------------------
 
@pytest.fixture
def servicio_basico(db, usuario_cliente):
    """Servicio publicado con campos mínimos requeridos."""
    return Servicio.objects.create(
        cliente=usuario_cliente,
        categoria="plomeria",
        titulo="Reparación de tubería",
        descripcion="Fuga en la cocina.",
        ciudad="Bogotá",
        direccion="Calle 10 # 20-30",
        barrio="La Candelaria",
        localidad="Centro",
        urgencia="media",
    )
 
 
@pytest.fixture
def aplicacion_pendiente(db, usuario_profesional, servicio_basico):
    """Aplicación de un profesional a un servicio, estado pendiente."""
    return Aplicacion.objects.create(
        profesional=usuario_profesional,
        servicio=servicio_basico,
        descripcion_trabajo="Puedo repararlo en una hora.",
    )
 
 
@pytest.fixture
def visita_pendiente(db, servicio_basico, usuario_profesional):
    """VisitaDiagnostico en estado pendiente."""
    return VisitaDiagnostico.objects.create(
        servicio=servicio_basico,
        profesional=usuario_profesional,
        fecha_propuesta=timezone.now() + timezone.timedelta(days=2),
        costo=Decimal("50000.00"),
    )
 
 
# ===========================================================================
# MODELO: Servicio
# ===========================================================================
 
class TestServicioCreacion:
    """Validar creación correcta del modelo Servicio."""
 
    def test_creacion_servicio_basico(self, servicio_basico):
        """El servicio debe persistir con los campos suministrados."""
        assert servicio_basico.pk is not None
        assert servicio_basico.titulo == "Reparación de tubería"
        assert servicio_basico.categoria == "plomeria"
 
    def test_estado_default_es_publicado(self, servicio_basico):
        """Un servicio nuevo debe tener estado 'publicado' por defecto."""
        assert servicio_basico.estado == "publicado"
 
    def test_requiere_visita_default_false(self, servicio_basico):
        """El campo requiere_visita debe ser False por defecto."""
        assert servicio_basico.requiere_visita is False
 
    def test_relacion_con_cliente(self, servicio_basico, usuario_cliente):
        """El servicio debe estar asociado al cliente correcto."""
        assert servicio_basico.cliente == usuario_cliente
 
    def test_imagen_opcional(self, servicio_basico):
        """El campo imagen puede estar vacío."""
        assert not servicio_basico.imagen
 
    def test_contrato_opcional(self, servicio_basico):
        """El campo contrato puede estar vacío."""
        assert not servicio_basico.contrato
 
    def test_metodo_pago_opcional(self, servicio_basico):
        """El campo metodo_pago puede ser nulo."""
        assert servicio_basico.metodo_pago is None
 
    def test_categorias_validas(self, db, usuario_cliente):
        """Todas las categorías del CHOICES deben ser aceptadas."""
        categorias = ["plomeria", "electricidad", "pintura", "limpieza", "otro"]
        for cat in categorias:
            s = Servicio.objects.create(
                cliente=usuario_cliente,
                categoria=cat,
                titulo=f"Servicio de {cat}",
                descripcion="Descripción de prueba.",
                ciudad="Bogotá",
                direccion="Calle 1",
                barrio="Chapinero",
                localidad="Norte",
                urgencia="baja",
            )
            assert s.categoria == cat
 
    def test_urgencias_validas(self, db, usuario_cliente):
        """Las tres urgencias (baja/media/alta) deben ser aceptadas."""
        for urgencia in ["baja", "media", "alta"]:
            s = Servicio.objects.create(
                cliente=usuario_cliente,
                categoria="otro",
                titulo=f"Urgencia {urgencia}",
                descripcion="Test.",
                ciudad="Bogotá",
                direccion="Calle 1",
                barrio="Sur",
                localidad="Sur",
                urgencia=urgencia,
            )
            assert s.urgencia == urgencia
 
    def test_str_incluye_titulo_y_nombre_cliente(self, servicio_basico):
        """__str__ debe incluir el título del servicio y el nombre del cliente."""
        resultado = str(servicio_basico)
        assert "Reparación de tubería" in resultado
        assert "Ana" in resultado
 
    def test_referencia_opcional(self, db, usuario_cliente):
        """El campo referencia puede estar vacío."""
        s = Servicio.objects.create(
            cliente=usuario_cliente,
            categoria="pintura",
            titulo="Pintura sin referencia",
            descripcion="Test.",
            ciudad="Bogotá",
            direccion="Calle 1",
            barrio="Sur",
            localidad="Sur",
            urgencia="baja",
            referencia=None,
        )
        assert s.referencia is None
 
 
# ===========================================================================
# MODELO: Aplicacion
# ===========================================================================
 
class TestAplicacionCreacion:
    """Validar creación y comportamiento del modelo Aplicacion."""
 
    def test_creacion_aplicacion(self, aplicacion_pendiente):
        """La aplicación debe persistir correctamente."""
        assert aplicacion_pendiente.pk is not None
 
    def test_estado_inicial_pendiente(self, aplicacion_pendiente):
        """Una nueva aplicación debe tener estado 'pendiente'."""
        assert aplicacion_pendiente.estado == "pendiente"
 
    def test_relacion_profesional_servicio(self, aplicacion_pendiente, usuario_profesional, servicio_basico):
        """La aplicación debe referenciar al profesional y al servicio correctos."""
        assert aplicacion_pendiente.profesional == usuario_profesional
        assert aplicacion_pendiente.servicio == servicio_basico
 
    def test_descripcion_trabajo_opcional(self, db, usuario_profesional, servicio_basico):
        """El campo descripcion_trabajo puede ser nulo."""
        app = Aplicacion.objects.create(
            profesional=usuario_profesional,
            servicio=servicio_basico,
            descripcion_trabajo=None,
        )
        assert app.descripcion_trabajo is None
 
    def test_cambio_estado_aceptado(self, aplicacion_pendiente):
        """El estado puede cambiar a 'aceptado'."""
        aplicacion_pendiente.estado = "aceptado"
        aplicacion_pendiente.save()
        aplicacion_pendiente.refresh_from_db()
        assert aplicacion_pendiente.estado == "aceptado"
 
    def test_cambio_estado_rechazado(self, aplicacion_pendiente):
        """El estado puede cambiar a 'rechazado'."""
        aplicacion_pendiente.estado = "rechazado"
        aplicacion_pendiente.save()
        aplicacion_pendiente.refresh_from_db()
        assert aplicacion_pendiente.estado == "rechazado"
 
    def test_str_incluye_profesional_y_servicio(self, aplicacion_pendiente):
        """__str__ debe incluir el nombre del profesional y el título del servicio."""
        resultado = str(aplicacion_pendiente)
        assert "Carlos" in resultado
        assert "Reparación de tubería" in resultado
 
 
# ===========================================================================
# MODELO: Evidencia
# ===========================================================================
 
class TestEvidenciaCreacion:
    """Validar el modelo Evidencia."""
 
    def test_creacion_evidencia_con_archivo(self, db, servicio_basico):
        """La evidencia debe asociarse al servicio y aceptar un archivo."""
        # Arrange — archivo en memoria
        archivo = SimpleUploadedFile(
            "foto_trabajo.jpg",
            b"contenido_binario_simulado",
            content_type="image/jpeg",
        )
        # Act
        evidencia = Evidencia.objects.create(
            servicio=servicio_basico,
            archivo=archivo,
        )
        # Assert
        assert evidencia.pk is not None
        assert evidencia.servicio == servicio_basico
 
    def test_evidencia_servicio_opcional(self, db):
        """El campo servicio en Evidencia puede ser nulo (null=True, blank=True)."""
        archivo = SimpleUploadedFile(
            "sin_servicio.pdf",
            b"datos",
            content_type="application/pdf",
        )
        evidencia = Evidencia.objects.create(
            servicio=None,
            archivo=archivo,
        )
        assert evidencia.servicio is None
 
    def test_evidencias_multiples_por_servicio(self, db, servicio_basico):
        """Un servicio puede tener varias evidencias."""
        for i in range(3):
            Evidencia.objects.create(
                servicio=servicio_basico,
                archivo=SimpleUploadedFile(f"foto_{i}.jpg", b"x", content_type="image/jpeg"),
            )
        total = Evidencia.objects.filter(servicio=servicio_basico).count()
        assert total == 3
 
 
# ===========================================================================
# MODELO: Calificacion
# ===========================================================================
 
class TestCalificacionCreacion:
    """Validar el modelo Calificacion."""
 
    def test_creacion_calificacion(self, db, usuario_cliente, usuario_profesional, servicio_basico):
        """La calificación debe persistir con cliente, profesional y servicio."""
        cal = Calificacion.objects.create(
            cliente=usuario_cliente,
            profesional=usuario_profesional,
            servicio=servicio_basico,
            puntuacion=5,
            comentario="Excelente trabajo.",
        )
        assert cal.pk is not None
        assert cal.puntuacion == 5
 
    def test_comentario_opcional(self, db, usuario_cliente, usuario_profesional, servicio_basico):
        """El campo comentario puede ser nulo."""
        cal = Calificacion.objects.create(
            cliente=usuario_cliente,
            profesional=usuario_profesional,
            servicio=servicio_basico,
            puntuacion=4,
            comentario=None,
        )
        assert cal.comentario is None
 
    def test_calificacion_onetoone_por_servicio(self, db, usuario_cliente, usuario_profesional, servicio_basico):
        """Solo puede existir una calificación por servicio (OneToOne)."""
        Calificacion.objects.create(
            cliente=usuario_cliente,
            profesional=usuario_profesional,
            servicio=servicio_basico,
            puntuacion=3,
        )
        with pytest.raises(IntegrityError):
            Calificacion.objects.create(
                cliente=usuario_cliente,
                profesional=usuario_profesional,
                servicio=servicio_basico,  # mismo servicio → viola OneToOne
                puntuacion=5,
            )
 
    def test_relacion_cliente_y_profesional(self, db, usuario_cliente, usuario_profesional, servicio_basico):
        """La calificación debe referenciar correctamente a cliente y profesional."""
        cal = Calificacion.objects.create(
            cliente=usuario_cliente,
            profesional=usuario_profesional,
            servicio=servicio_basico,
            puntuacion=5,
        )
        assert cal.cliente == usuario_cliente
        assert cal.profesional == usuario_profesional
 
    def test_str_incluye_puntuacion_y_profesional(self, db, usuario_cliente, usuario_profesional, servicio_basico):
        """__str__ debe incluir la puntuación y el nombre del profesional."""
        cal = Calificacion.objects.create(
            cliente=usuario_cliente,
            profesional=usuario_profesional,
            servicio=servicio_basico,
            puntuacion=5,
        )
        resultado = str(cal)
        assert "5" in resultado
        assert "Carlos" in resultado
 
 
# ===========================================================================
# MODELO: VisitaDiagnostico
# ===========================================================================
 
class TestVisitaDiagnosticoCreacion:
    """Validar el modelo VisitaDiagnostico."""
 
    def test_creacion_visita(self, visita_pendiente):
        """La visita debe persistir con sus campos básicos."""
        assert visita_pendiente.pk is not None
        assert visita_pendiente.costo == Decimal("50000.00")
 
    def test_estado_inicial_pendiente(self, visita_pendiente):
        """Una nueva visita debe tener estado 'pendiente'."""
        assert visita_pendiente.estado == "pendiente"
 
    def test_relacion_con_servicio_y_profesional(self, visita_pendiente, servicio_basico, usuario_profesional):
        """La visita debe estar asociada al servicio y profesional correctos."""
        assert visita_pendiente.servicio == servicio_basico
        assert visita_pendiente.profesional == usuario_profesional
 
    def test_cambio_estado_aceptada(self, visita_pendiente):
        """El estado puede cambiar a 'aceptada'."""
        visita_pendiente.estado = "aceptada"
        visita_pendiente.save()
        visita_pendiente.refresh_from_db()
        assert visita_pendiente.estado == "aceptada"
 
    def test_cambio_estado_rechazada(self, visita_pendiente):
        """El estado puede cambiar a 'rechazada'."""
        visita_pendiente.estado = "rechazada"
        visita_pendiente.save()
        visita_pendiente.refresh_from_db()
        assert visita_pendiente.estado == "rechazada"
 
    def test_costo_decimal_preciso(self, db, servicio_basico, usuario_profesional):
        """El costo debe almacenar correctamente hasta 2 decimales."""
        visita = VisitaDiagnostico.objects.create(
            servicio=servicio_basico,
            profesional=usuario_profesional,
            fecha_propuesta=timezone.now() + timezone.timedelta(days=1),
            costo=Decimal("123456.78"),
        )
        visita.refresh_from_db()
        assert visita.costo == Decimal("123456.78")
 
    def test_multiples_visitas_por_servicio(self, db, servicio_basico, usuario_profesional):
        """Un servicio puede tener múltiples visitas de diagnóstico."""
        for i in range(3):
            VisitaDiagnostico.objects.create(
                servicio=servicio_basico,
                profesional=usuario_profesional,
                fecha_propuesta=timezone.now() + timezone.timedelta(days=i + 1),
                costo=Decimal("30000.00"),
            )
        total = VisitaDiagnostico.objects.filter(servicio=servicio_basico).count()
        assert total == 3