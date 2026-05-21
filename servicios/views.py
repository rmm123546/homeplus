from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .models import Evidencia
from .models import Reprogramacion
from reportlab.lib.styles import getSampleStyleSheet
from django.http import HttpResponse
from .models import Calificacion
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from usuarios.models import Usuario, PerfilProfesional
from .models import Servicio, Aplicacion, Calificacion, VisitaDiagnostico
from .forms import ServicioForm
from django.db.models import Avg
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
import csv
import requests
from django.core.files.base import ContentFile
from django.shortcuts import render, get_object_or_404
from usuarios.models import Usuario, PerfilProfesional
from .models import Calificacion
from django.db.models import Avg
from django.shortcuts import render, redirect
from usuarios.models import PerfilProfesional
from .models import Evidencia
from django.shortcuts import get_object_or_404, redirect
from .models import Aplicacion
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from django.shortcuts import redirect
from .models import Disponibilidad
# ─────────────────────────────────────────
# DASHBOARD CLIENTE
# ─────────────────────────────────────────
@never_cache
def dashboard(request):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id']
    )

    # 🔥 Si es profesional → redirigir
    if usuario.tipo_usuario == 'profesional':
        return redirect('servicios:dashboard_profesional')

    # 🔵 TODOS LOS SERVICIOS
    servicios = Servicio.objects.filter(cliente=usuario)

    # 🟡 SOLO EDITABLES
    servicios_editar = servicios.exclude(
        estado='finalizado',
        calificacion__isnull=False
    )

    # 🔍 BUSCADOR
    query = request.GET.get('q')
    if query:
        servicios = servicios.filter(titulo__icontains=query)

    # 🎯 FILTROS
    urgencia = request.GET.get('urgencia')
    if urgencia:
        servicios = servicios.filter(urgencia=urgencia)

    estado = request.GET.get('estado')
    if estado:
        servicios = servicios.filter(estado=estado)

    categoria = request.GET.get('categoria')
    if categoria:
        servicios = servicios.filter(categoria=categoria)

    ciudad = request.GET.get('ciudad')
    if ciudad:
        servicios = servicios.filter(ciudad__icontains=ciudad)

    servicios = servicios.order_by('-id_servicio')

    # 🧾 CREAR SERVICIO
    if request.method == 'POST':

        data = request.POST.copy()

        if not data.get('requiere_visita'):
            data['fecha_visita'] = ''

        form = ServicioForm(data, request.FILES)

        if form.is_valid():
            servicio = form.save(commit=False)
            servicio.cliente = usuario
            servicio.estado = 'publicado'

            if not servicio.requiere_visita:
                servicio.fecha_visita = None

            servicio.save()

            messages.success(request, 'Servicio publicado correctamente.')
            return redirect('servicios:dashboard')
    else:
        form = ServicioForm()

    # 🔥 DISPONIBILIDAD (CORREGIDO)
    usuario = get_object_or_404(
        Usuario,
        id_usuario=request.session['usuario_id']
    )

    disponibilidades = Disponibilidad.objects.filter(
        profesional=usuario
    ).order_by('-id')
    return render(request, 'servicios/dashboard.html', {
        'usuario': usuario,
        'servicios': servicios,
        'servicios_editar': servicios_editar,
        'form': form,
        'disponibilidades': disponibilidades
    })
# ─────────────────────────────────────────
# CARGA MASIVA
# ────────────────────────────────────────


def carga_masiva(request):
    if request.method == "POST":
        archivo = request.FILES.get("archivo")
        if not archivo:
            messages.error(request, "No se subió ningún archivo.")
            return redirect("servicios:dashboard")

        if not archivo.name.endswith(".csv"):
            messages.error(request, "El archivo debe ser un CSV.")
            return redirect("servicios:dashboard")

        usuario = get_object_or_404(
            Usuario, id_usuario=request.session['usuario_id'])

        try:
            archivo_decodificado = archivo.read().decode("utf-8").splitlines()
            reader = csv.DictReader(archivo_decodificado)

            for fila in reader:
                if not fila.get("titulo") or not fila.get("descripcion") or not fila.get("categoria"):
                    continue  # saltar fila si falta algo

                servicio = Servicio(
                    titulo=fila["titulo"],
                    descripcion=fila["descripcion"],
                    categoria=fila["categoria"],
                    urgencia=fila.get("urgencia", "baja"),
                    cliente=usuario,
                    ciudad=fila.get("ciudad", "Bogotá"),
                    direccion=fila.get("direccion", ""),
                    referencia=fila.get("referencia", ""),
                    estado='publicado',
                    localidad=fila.get("localidad",""),
                    barrio=fila.get("barrio","")
                )

                # ⚡ Manejar URL de imagen
                url_imagen = fila.get("imagen_url")
                if url_imagen:
                    try:
                        respuesta = requests.get(url_imagen)
                        if respuesta.status_code == 200:
                            nombre_imagen = url_imagen.split("/")[-1]
                            servicio.imagen.save(nombre_imagen, ContentFile(
                                respuesta.content), save=False)
                    except Exception as e:
                        print(
                            f"No se pudo descargar la imagen: {url_imagen} - {e}")

                servicio.save()

            messages.success(
                request, "Servicios cargados correctamente con imágenes (si había URLs).")

        except Exception as e:
            messages.error(request, f"Error al cargar archivo: {e}")

        return redirect("servicios:dashboard")

# ─────────────────────────────────────────
# EDITAR SERVICIO
# ─────────────────────────────────────────


@never_cache
def editar_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    servicio = get_object_or_404(
        Servicio, id_servicio=id, cliente=usuario)

    # 🔒 BLOQUEO DE EDICIÓN
    if servicio.estado != 'publicado':
        messages.error(
            request, "No puedes editar este servicio en su estado actual.")
        return redirect('servicios:dashboard')

    if request.method == 'POST':

        data = request.POST.copy()

        if not data.get('requiere_visita'):
            data['fecha_visita'] = ''

        form = ServicioForm(data, request.FILES, instance=servicio)

        if form.is_valid():

            servicio_editado = form.save(commit=False)

            nueva_imagen = request.FILES.get('imagen')

            if nueva_imagen:
                servicio_editado.imagen = nueva_imagen
            else:
                servicio_editado.imagen = servicio.imagen

            if not servicio_editado.imagen:
                messages.error(
                    request, "Debes subir una imagen obligatoriamente.")
                return redirect(request.path)

            if not servicio_editado.requiere_visita:
                servicio_editado.fecha_visita = None

            servicio_editado.save()

            messages.success(
                request, 'Servicio actualizado correctamente.')
            return redirect('servicios:dashboard')

        else:
            print("ERROR EDITAR:", form.errors)

    else:
        form = ServicioForm(instance=servicio)

    return render(request, 'servicios/editar_servicio.html', {
        'form': form,
        'servicio': servicio
    })


# ─────────────────────────────────────────
# ELIMINAR SERVICIO
# ─────────────────────────────────────────
@never_cache
def eliminar_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    servicio = get_object_or_404(
        Servicio, id_servicio=id, cliente=usuario)

    if request.method == 'POST':
        servicio.delete()
        messages.success(request, 'Servicio eliminado correctamente.')
        return redirect('servicios:dashboard')

    return render(request, 'servicios/eliminar_servicio.html', {
        'servicio': servicio
    })


# ─────────────────────────────────────────
# DASHBOARD PROFESIONAL
# ─────────────────────────────────────────
@never_cache
def dashboard_profesional(request):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    if usuario.tipo_usuario != 'profesional':
        return redirect('servicios:dashboard')

    perfil = PerfilProfesional.objects.filter(usuario=usuario).first()

    servicios = Servicio.objects.all()

    aplicaciones = Aplicacion.objects.filter(profesional=usuario)

    servicios_postulados_ids = aplicaciones.values_list('servicio_id', flat=True)

    servicios = servicios.exclude(id_servicio__in=servicios_postulados_ids)

    promedio = Calificacion.objects.filter(
        profesional=usuario
    ).aggregate(Avg('puntuacion'))['puntuacion__avg']

    evidencias = Evidencia.objects.filter(
        servicio__aplicaciones__profesional=usuario
    ).distinct()

    # 🔥 AQUÍ ESTABA EL ERROR
    disponibilidades = Disponibilidad.objects.filter(
        profesional=usuario
    ).order_by('-id')

    return render(request, 'servicios/dashboard_profesional.html', {
        'usuario': usuario,
        'perfil': perfil,
        'servicios': servicios,
        'promedio': promedio,
        'aplicaciones': aplicaciones,
        'evidencias': evidencias,
        'disponibilidades': disponibilidades,
    })

def detalle_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    if usuario.tipo_usuario != 'profesional':
        return redirect('servicios:dashboard')

    servicio = get_object_or_404(Servicio, id_servicio=id)

    visita = None
    if servicio.requiere_visita:
        visita = VisitaDiagnostico.objects.filter(servicio=servicio).first()

    return render(request, 'servicios/detalle_servicio.html', {
        'servicio': servicio,
        'usuario': usuario,
        'visita': visita
    })


def aplicar_servicio(request, servicio_id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
    servicio = get_object_or_404(Servicio, id_servicio=servicio_id)

    # 🔥 evitar duplicados
    if Aplicacion.objects.filter(profesional=usuario, servicio=servicio).exists():
        messages.warning(request, "Ya aplicaste a este servicio")
        return redirect('servicios:dashboard_profesional')

    if request.method == 'POST':

        fecha = request.POST.get('fecha_propuesta')
        costo = request.POST.get('costo')

        # ✅ VALIDAR SOLO SI REQUIERE VISITA
        if servicio.requiere_visita:
            if not fecha or not costo:
                messages.error(request, "Debes ingresar fecha y costo")
                return redirect('servicios:detalle', servicio.id_servicio)

        # 🔥 crear aplicación
        Aplicacion.objects.create(
            profesional=usuario,
            servicio=servicio
        )

        # 🔥 crear visita SOLO si aplica
        if servicio.requiere_visita:

            VisitaDiagnostico.objects.create(
                servicio=servicio,
                profesional=usuario,
                fecha_propuesta=fecha,
                costo=costo,
                estado='pendiente'
            )

        messages.success(request, "Aplicaste correctamente")
        return redirect('servicios:dashboard_profesional')


def ver_aplicaciones(request, servicio_id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    servicio = get_object_or_404(
        Servicio, id_servicio=servicio_id, cliente=usuario)

    aplicaciones = Aplicacion.objects.filter(servicio=servicio)

    data = []

    for app in aplicaciones:

        visita = VisitaDiagnostico.objects.filter(
            servicio=servicio,
            profesional=app.profesional
        ).first()

        # ⭐ promedio de calificación
        promedio = Calificacion.objects.filter(
            profesional=app.profesional
        ).aggregate(Avg('puntuacion'))['puntuacion__avg']

        data.append({
            'aplicacion': app,
            'visita': visita,
            'promedio': promedio
        })

    # 🔎 FILTRO
    filtro = request.GET.get('filtro')

    if filtro == 'precio':
        data = sorted(
            data,
            key=lambda x: x['visita'].costo if x['visita'] else 999999
        )

    elif filtro == 'fecha':
        data = sorted(
            data,
            key=lambda x: x['visita'].fecha_propuesta if x['visita'] else ''
        )

    elif filtro == 'calificacion':
        data = sorted(
            data,
            key=lambda x: x['promedio'] if x['promedio'] else 0,
            reverse=True
        )

    return render(request, 'servicios/aplicaciones.html', {
        'servicio': servicio,
        'data': data,
        'filtro': filtro
    })


def aceptar_profesional(request, aplicacion_id):

    aplicacion = get_object_or_404(Aplicacion, id=aplicacion_id)
    servicio = aplicacion.servicio

    # 🔥 poner todos en rechazado
    Aplicacion.objects.filter(servicio=servicio).update(estado='rechazado')

    # 🔥 aceptar el seleccionado
    aplicacion.estado = 'aceptado'
    aplicacion.save()

    # 🔥 cambiar estado del servicio
    servicio.estado = 'proceso'
    servicio.save()

    messages.success(request, "Profesional seleccionado correctamente")
    return redirect('servicios:dashboard')


def subir_contrato(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    servicio = get_object_or_404(Servicio, id_servicio=id)

    if request.method == 'POST':
        archivo = request.FILES.get('contrato')

        if archivo:
            servicio.contrato = archivo
            servicio.estado = 'proceso'
            servicio.save()

    return redirect('servicios:seguimiento', id=servicio.id_servicio)


def finalizar_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    servicio = get_object_or_404(Servicio, id_servicio=id)

    servicio.estado = 'finalizado'
    servicio.save()

    return redirect('servicios:dashboard')


def seguimiento_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id'])

    servicio = get_object_or_404(Servicio, id_servicio=id)

    # 🔒 Seguridad
    if usuario.tipo_usuario == 'cliente' and servicio.cliente != usuario:
        return redirect('servicios:dashboard')

    visita = None
    if servicio.requiere_visita:
        visita = VisitaDiagnostico.objects.filter(servicio=servicio).first()

    return render(request, 'servicios/seguimiento_servicio.html', {
        'servicio': servicio,
        'usuario': usuario,
        'visita': visita
    })


def subir_evidencia(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    servicio = get_object_or_404(Servicio, id_servicio=id)

    if request.method == 'POST':
        archivo = request.FILES.get('evidencia')

        if archivo:
            Evidencia.objects.create(
                servicio=servicio,
                archivo=archivo
            )

    return redirect('servicios:seguimiento', id=servicio.id_servicio)


def calificar_servicio(request, id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])

    servicio = get_object_or_404(Servicio, id_servicio=id, cliente=usuario)

    # 🔥 solo servicios finalizados
    if servicio.estado != 'finalizado':
        return redirect('servicios:dashboard')

    # 🔥 evitar doble calificación
    if Calificacion.objects.filter(servicio=servicio).exists():
        messages.info(request, 'Ya calificaste este servicio.')
        return redirect('servicios:dashboard')

    if request.method == 'POST':
        puntuacion = int(request.POST.get('puntuacion'))
        comentario = request.POST.get('comentario')

        aplicacion = servicio.aplicaciones.filter(estado='aceptado').first()

        if not aplicacion:
            messages.error(request, 'No hay profesional asignado.')
            return redirect('servicios:dashboard')

        Calificacion.objects.create(
            cliente=usuario,
            profesional=aplicacion.profesional,
            servicio=servicio,
            puntuacion=puntuacion,
            comentario=comentario
        )

        messages.success(request, 'Calificación enviada.')
        return redirect('servicios:dashboard')

    return render(request, 'servicios/calificar.html', {
        'servicio': servicio
    })


def gestionar_visita(request, servicio_id):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])
    servicio = get_object_or_404(Servicio, id_servicio=servicio_id)

    if request.method == 'POST':

        fecha = request.POST.get('fecha_propuesta')
        costo = request.POST.get('costo')

        if not fecha or not costo:
            messages.error(request, "Debes ingresar fecha y costo")
            return redirect('servicios:detalle', servicio.id_servicio)

        visita, creada = VisitaDiagnostico.objects.get_or_create(
            servicio=servicio,
            profesional=usuario,
            defaults={
                'fecha_propuesta': fecha,
                'costo': costo
            }
        )

        if not creada:
            visita.fecha_propuesta = fecha
            visita.costo = costo
            visita.estado = 'pendiente'
            visita.save()

        messages.success(request, "Propuesta de visita enviada")
        return redirect('servicios:dashboard_profesional')


def reprogramar(request, id):

    servicio = Servicio.objects.get(id_servicio=id)

    if request.method == 'POST':
        nueva_fecha = request.POST.get('fecha')

        Reprogramacion.objects.create(
            servicio=servicio,
            profesional=request.user,
            nueva_fecha=nueva_fecha
        )

        return redirect('servicios:dashboard_profesional')


def seleccionar_pago(request, servicio_id):

    servicio = get_object_or_404(Servicio, id_servicio=servicio_id)

    if request.method == 'POST':
        metodo = request.POST.get('metodo_pago')

        if not metodo:
            messages.error(request, "Selecciona un método de pago")
            return redirect('servicios:seguimiento', servicio.id_servicio)

        servicio.metodo_pago = metodo
        servicio.save()

        messages.success(request, "Método de pago confirmado")
        return redirect('servicios:seguimiento', servicio.id_servicio)


def generar_contrato(request, servicio_id):

    servicio = get_object_or_404(Servicio, id_servicio=servicio_id)

    # 🔥 Obtener profesional desde la aplicación aceptada
    aplicacion = servicio.aplicaciones.filter(estado="aceptado").first()
    if not aplicacion.descripcion_trabajo:
        messages.error(request, "El profesional debe registrar la descripción del trabajo antes de generar el contrato.", extra_tags='contrato')
        return redirect('servicios:seguimiento', id=servicio.id_servicio)
    
    profesional = aplicacion.profesional if aplicacion else None
    descripcion_trabajo = aplicacion.descripcion_trabajo if aplicacion else None
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="contrato_servicio.pdf"'

    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()

    contenido = []

    # 🔥 TÍTULO
    contenido.append(Paragraph("CONTRATO DE PRESTACIÓN DE SERVICIOS", styles['Title']))
    contenido.append(Spacer(1, 20))

    fecha = datetime.now().strftime("%d/%m/%Y")

    contenido.append(Paragraph(f"Fecha de generación: {fecha}", styles['Normal']))
    contenido.append(Spacer(1, 12))

    # 🔥 PARTES
    contenido.append(Paragraph("<b>PARTES DEL CONTRATO</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        f"<b>Cliente:</b> {servicio.cliente.nombre} {servicio.cliente.apellido}", styles['Normal']))
    
    if profesional:
        contenido.append(Paragraph(
            f"<b>Profesional:</b> {profesional.nombre} {profesional.apellido}", styles['Normal']))
    else:
        contenido.append(Paragraph(
            "<b>Profesional:</b> No asignado aún", styles['Normal']))

    contenido.append(Spacer(1, 20))

    # 🔥 OBJETO DEL CONTRATO
    contenido.append(Paragraph("<b>OBJETO DEL CONTRATO</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        f"El presente contrato tiene como objeto la prestación del servicio denominado "
        f"'{servicio.titulo}', el cual consiste en: {servicio.descripcion}.",
        styles['Normal']))
    
    contenido.append(Spacer(1, 20))

    # 🔥 CONDICIONES DEL SERVICIO
    contenido.append(Paragraph("<b>CONDICIONES DEL SERVICIO</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        f"Categoría: {servicio.get_categoria_display()}<br/>"
        f"Urgencia: {servicio.get_urgencia_display()}<br/>"
        f"Dirección: {servicio.direccion}<br/>"
        f"Ciudad: {servicio.ciudad}",
        styles['Normal']))

    contenido.append(Spacer(1, 20))

    contenido.append(Paragraph("<b>CONDICIONES DE PAGO</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    # ✅ definir método de pago antes
    if servicio.metodo_pago:
        metodo_pago = servicio.get_metodo_pago_display()
    else:
        metodo_pago = "Pendiente por definir"

    # ✅ usarlo en el texto
    contenido.append(Paragraph(
        f"El pago del servicio se realizará mediante el método: {metodo_pago}. "
        "Las condiciones económicas serán acordadas entre las partes antes del inicio del servicio.",
        styles['Normal']))

    contenido.append(Spacer(1, 20))

    # 🔥 OBLIGACIONES
    contenido.append(Paragraph("<b>OBLIGACIONES DE LAS PARTES</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        "<b>Del Profesional:</b><br/>"
        "- Ejecutar el servicio de manera responsable y profesional.<br/>"
        "- Cumplir con los tiempos acordados.<br/>"
        "- Garantizar la calidad del servicio prestado.<br/><br/>"
        "<b>Del Cliente:</b><br/>"
        "- Facilitar el acceso al lugar del servicio.<br/>"
        "- Realizar el pago en las condiciones acordadas.<br/>"
        "- Brindar información veraz sobre el servicio solicitado.",
        styles['Normal']))

    contenido.append(Spacer(1, 20))

    # 🔥 DESCRIPCIÓN DEL TRABAJO
    contenido.append(Paragraph("<b>DESCRIPCIÓN DEL TRABAJO A REALIZAR</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    if descripcion_trabajo:
        contenido.append(Paragraph(
            f"{descripcion_trabajo}",
            styles['Normal']
        ))
    else:
        contenido.append(Paragraph(
            "El profesional no ha registrado aún una descripción detallada del trabajo.",
            styles['Normal']
        ))
    
    contenido.append(Spacer(1, 20))
    # 🔥 DURACIÓN
    contenido.append(Paragraph("<b>DURACIÓN DEL CONTRATO</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        "El presente contrato tendrá vigencia desde su aceptación hasta la finalización del servicio contratado.",
        styles['Normal']))

    contenido.append(Spacer(1, 20))

    # 🔥 TERMINACIÓN
    contenido.append(Paragraph("<b>TERMINACIÓN</b>", styles['Heading2']))
    contenido.append(Spacer(1, 10))

    contenido.append(Paragraph(
        "El contrato podrá darse por terminado por mutuo acuerdo entre las partes o por incumplimiento "
        "de cualquiera de las obligaciones aquí establecidas.",
        styles['Normal']))

    contenido.append(Spacer(1, 30))

    # 🔥 FIRMAS
    contenido.append(Paragraph("<b>FIRMAS</b>", styles['Heading2']))
    contenido.append(Spacer(1, 40))

    contenido.append(Paragraph(
        "_____________________________<br/>Firma Cliente",
        styles['Normal']))
    
    contenido.append(Spacer(1, 30))

    contenido.append(Paragraph(
        "_____________________________<br/>Firma Profesional",
        styles['Normal']))

    # 🔥 GENERAR PDF
    doc.build(contenido)

    return response
# ─────────────────────────────────────────
# cerrar sesion
# ─────────────────────────────────────────


@never_cache
def cerrar_sesion(request):
    logout(request)
    request.session.flush()  # 🔥 destruye completamente la sesión
    return redirect('usuarios:landing')

def ver_perfil_profesional(request, id):

    usuario = get_object_or_404(Usuario, id_usuario=id)
    perfil = get_object_or_404(PerfilProfesional, usuario=usuario)

    calificaciones = Calificacion.objects.filter(profesional=usuario)
    promedio = calificaciones.aggregate(prom=Avg('puntuacion'))['prom']

    evidencias = Evidencia.objects.all().order_by('-id')[:6]

    # ✅ AQUI LA DISPONIBILIDAD
    disponibilidades = Disponibilidad.objects.filter(
        profesional=usuario
    ).order_by('dia', 'hora_inicio')

    return render(request, 'servicios/perfil_profesional.html', {
        'usuario': usuario,
        'perfil': perfil,
        'calificaciones': calificaciones,
        'promedio': promedio,
        'evidencias': evidencias,
        'disponibilidades': disponibilidades
    })
        

def editar_perfil(request):

    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario, id_usuario=request.session['usuario_id']
    )

    perfil = PerfilProfesional.objects.get(usuario=usuario)

    # 🔥 TRAER EVIDENCIAS CORRECTAMENTE
    evidencias = Evidencia.objects.filter(
        servicio__aplicaciones__profesional=usuario
    ).distinct()

    if request.method == 'POST':

        perfil.servicio_descripcion = request.POST.get('descripcion')
        perfil.historial = request.POST.get('historial')
        perfil.certificaciones = request.POST.get('certificaciones')

        perfil.save()

        # 🔥 GUARDAR IMÁGENES CORRECTAMENTE
        archivos = request.FILES.getlist('imagenes')

        # 🔥 BUSCAR UN SERVICIO REAL DEL PROFESIONAL
        servicio = Servicio.objects.filter(
            aplicaciones__profesional=usuario
        ).last()

        for archivo in archivos:
            if servicio:  # evitar guardar sin relación
                Evidencia.objects.create(
                    servicio=servicio,
                    archivo=archivo
                )

        return redirect('servicios:dashboard_profesional')

    return render(request, 'servicios/editar_perfil.html', {
        'perfil': perfil,
        'evidencias': evidencias
    })
    
def cancelar_postulacion(request, id):
        if 'usuario_id' not in request.session:
            return redirect('usuarios:login')

        aplicacion = get_object_or_404(Aplicacion, id=id)

        # Seguridad: solo el dueño puede cancelar
        if aplicacion.profesional.id_usuario != request.session['usuario_id']:
            return redirect('servicios:dashboard_profesional')

        aplicacion.delete()

        return redirect('servicios:dashboard_profesional')

from .models import Disponibilidad

def crear_disponibilidad(request):

    # 🔥 VALIDAR SESIÓN
    if 'usuario_id' not in request.session:
        return redirect('usuarios:login')

    usuario = get_object_or_404(
        Usuario,
        id_usuario=request.session['usuario_id']
    )

    if request.method == "POST":
        dia = request.POST["dia"]
        hora_inicio = request.POST["hora_inicio"]
        hora_fin = request.POST["hora_fin"]

        usuario = Usuario.objects.get(id_usuario=request.session['usuario_id'])

        Disponibilidad.objects.create(
            profesional=usuario,
            dia=dia,
            hora_inicio=hora_inicio,
            hora_fin=hora_fin
        )

    return redirect("servicios:dashboard")


from django.shortcuts import get_object_or_404, redirect
from .models import Aplicacion

def guardar_descripcion_trabajo(request, id):
    aplicacion = get_object_or_404(Aplicacion, id=id)

    if request.method == "POST":
        aplicacion.descripcion_trabajo = request.POST.get("descripcion_trabajo")
        aplicacion.save()

    return redirect("servicios:dashboard_profesional")