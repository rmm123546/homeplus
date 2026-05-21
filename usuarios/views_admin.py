"""
HOME+ — Panel de Administración Propio
Solo accesible para usuarios con tipo_usuario = 'admin'.
"""

import io
import json
from datetime import date, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import HttpResponse

from .models import Usuario, PerfilProfesional, ReporteAdmin


# ─────────────────────────────────────────────────────────────
# DECORADOR: proteger vistas de admin
# ─────────────────────────────────────────────────────────────

def admin_requerido(func):
    def wrapper(request, *args, **kwargs):
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            messages.error(request, 'Debes iniciar sesión.')
            return redirect('usuarios:login')
        try:
            admin = Usuario.objects.get(id_usuario=usuario_id, tipo_usuario='admin')
        except Usuario.DoesNotExist:
            messages.error(request, 'No tienes permisos para acceder al panel.')
            return redirect('usuarios:login')
        return func(request, *args, admin=admin, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_dashboard(request, admin):
    hoy = date.today()

    stats = {
        'total':         Usuario.objects.exclude(tipo_usuario='admin').count(),
        'clientes':      Usuario.objects.filter(tipo_usuario='cliente').count(),
        'profesionales': Usuario.objects.filter(tipo_usuario='profesional').count(),
        'pendientes':    Usuario.objects.filter(estado_cuenta='pendiente', activo=True).count(),
        'aprobados':     Usuario.objects.filter(estado_cuenta='aprobado').count(),
        'rechazados':    Usuario.objects.filter(estado_cuenta='rechazado').count(),
        'sin_activar':   Usuario.objects.filter(activo=False, tipo_usuario__in=['cliente','profesional']).count(),
        'hoy':           Usuario.objects.filter(fecha_registro__date=hoy).exclude(tipo_usuario='admin').count(),
    }

    # Registros últimos 7 días para gráfica
    semana = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        semana.append({
            'dia': dia.strftime('%d/%m'),
            'cantidad': Usuario.objects.filter(fecha_registro__date=dia).exclude(tipo_usuario='admin').count()
        })

    ultimos_pendientes = (
        Usuario.objects
        .filter(estado_cuenta='pendiente', activo=True)
        .exclude(tipo_usuario='admin')
        .order_by('-fecha_registro')[:6]
    )

    servicios = (
        PerfilProfesional.objects
        .values('servicio')
        .annotate(total=Count('servicio'))
        .order_by('-total')[:6]
    )

    ultimos_reportes = ReporteAdmin.objects.order_by('-fecha_creacion')[:4]

    return render(request, 'usuarios/admin/dashboard.html', {
        'admin': admin,
        'stats': stats,
        'semana_json': json.dumps(semana),
        'ultimos_pendientes': ultimos_pendientes,
        'servicios': servicios,
        'ultimos_reportes': ultimos_reportes,
    })


# ─────────────────────────────────────────────────────────────
# LISTA DE USUARIOS
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_usuarios(request, admin):
    qs = Usuario.objects.exclude(tipo_usuario='admin').order_by('-fecha_registro')

    tipo    = request.GET.get('tipo', '')
    estado  = request.GET.get('estado', '')
    activo  = request.GET.get('activo', '')
    q       = request.GET.get('q', '').strip()

    if tipo:    qs = qs.filter(tipo_usuario=tipo)
    if estado:  qs = qs.filter(estado_cuenta=estado)
    if activo == '1': qs = qs.filter(activo=True)
    elif activo == '0': qs = qs.filter(activo=False)
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) | Q(apellido__icontains=q) |
            Q(correo__icontains=q) | Q(telefono__icontains=q)
        )

    return render(request, 'usuarios/admin/usuarios.html', {
        'admin': admin, 'usuarios': qs, 'total': qs.count(),
        'tipo': tipo, 'estado': estado, 'activo': activo, 'q': q,
    })


# ─────────────────────────────────────────────────────────────
# DETALLE DE USUARIO
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_usuario_detalle(request, usuario_id, admin):
    usuario = get_object_or_404(Usuario, id_usuario=usuario_id)
    perfil  = getattr(usuario, 'perfil_profesional', None)
    return render(request, 'usuarios/admin/usuario_detalle.html', {
        'admin': admin, 'usuario': usuario, 'perfil': perfil,
    })


# ─────────────────────────────────────────────────────────────
# APROBAR / RECHAZAR
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_aprobar(request, usuario_id, admin):
    u = get_object_or_404(Usuario, id_usuario=usuario_id)
    u.estado_cuenta = 'aprobado'
    u.save()
    messages.success(request, f'✅ Cuenta de {u.nombre} {u.apellido} aprobada.')
    return redirect(request.META.get('HTTP_REFERER', 'usuarios:admin_usuarios'))


@admin_requerido
def admin_rechazar(request, usuario_id, admin):
    u = get_object_or_404(Usuario, id_usuario=usuario_id)
    u.estado_cuenta = 'rechazado'
    u.save()
    messages.warning(request, f'❌ Cuenta de {u.nombre} {u.apellido} rechazada.')
    return redirect(request.META.get('HTTP_REFERER', 'usuarios:admin_usuarios'))


@admin_requerido
def admin_aprobar_masivo(request, admin):
    if request.method == 'POST':
        ids    = request.POST.getlist('ids')
        accion = request.POST.get('accion')
        if not ids:
            messages.error(request, 'No seleccionaste ningún usuario.')
            return redirect('usuarios:admin_usuarios')
        estado = 'aprobado' if accion == 'aprobar' else 'rechazado'
        n = Usuario.objects.filter(id_usuario__in=ids).update(estado_cuenta=estado)
        messages.success(request, f'{n} usuario(s) {"aprobados" if estado=="aprobado" else "rechazados"}.')
    return redirect('usuarios:admin_usuarios')


# ─────────────────────────────────────────────────────────────
# REPORTES
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_reportes(request, admin):
    reportes = ReporteAdmin.objects.order_by('-fecha_creacion')
    return render(request, 'usuarios/admin/reportes.html', {
        'admin': admin, 'reportes': reportes,
    })


@admin_requerido
def admin_crear_reporte(request, admin):
    if request.method == 'POST':
        titulo      = request.POST.get('titulo', '').strip()
        tipo        = request.POST.get('tipo', 'general')
        descripcion = request.POST.get('descripcion', '').strip()
        if not titulo:
            messages.error(request, 'El título es obligatorio.')
            return render(request, 'usuarios/admin/crear_reporte.html', {'admin': admin})

        filtros = {
            'fecha_desde':   request.POST.get('fecha_desde', '').strip(),
            'fecha_hasta':   request.POST.get('fecha_hasta', '').strip(),
            'tipo_usuario':  request.POST.get('tipo_usuario', '').strip(),
            'estado_cuenta': request.POST.get('estado_cuenta', '').strip(),
            'tipo_servicio': request.POST.get('tipo_servicio', '').strip(),
            'ciudad':        request.POST.get('ciudad', '').strip(),
        }
        # Quitar filtros vacíos
        filtros = {k: v for k, v in filtros.items() if v}

        datos = _generar_datos(tipo, filtros)
        datos['filtros_aplicados'] = filtros  # guardar para mostrarlo en el detalle y PDF

        reporte = ReporteAdmin.objects.create(
            titulo=titulo, tipo=tipo, descripcion=descripcion,
            creado_por=admin,
            datos_json=json.dumps(datos, ensure_ascii=False, default=str)
        )
        messages.success(request, f'Reporte "{titulo}" generado.')
        return redirect('usuarios:admin_reporte_detalle', reporte_id=reporte.pk)

    return render(request, 'usuarios/admin/crear_reporte.html', {'admin': admin})


def _generar_datos(tipo, filtros=None):
    from servicios.models import Servicio
    from datetime import datetime
    try:
        import pytz
        bogota = pytz.timezone('America/Bogota')
        def localizar(dt): return bogota.localize(dt)
    except ImportError:
        from zoneinfo import ZoneInfo
        bogota_zi = ZoneInfo('America/Bogota')
        def localizar(dt): return dt.replace(tzinfo=bogota_zi)

    # Convertir fechas de texto a datetimes con zona horaria de Bogotá
    # Esto evita el problema de UTC vs hora local con USE_TZ=True
    filtros = filtros or {}
    hoy = date.today()

    def fecha_inicio(fecha_str):
        d = datetime.strptime(fecha_str, '%Y-%m-%d')
        return localizar(d.replace(hour=0, minute=0, second=0, microsecond=0))

    def fecha_fin(fecha_str):
        d = datetime.strptime(fecha_str, '%Y-%m-%d')
        return localizar(d.replace(hour=23, minute=59, second=59, microsecond=999999))

    # ── Base queryset usuarios ────────────────────────────────
    qs_usuarios = Usuario.objects.exclude(tipo_usuario='admin')

    if filtros.get('fecha_desde'):
        qs_usuarios = qs_usuarios.filter(fecha_registro__gte=fecha_inicio(filtros['fecha_desde']))
    if filtros.get('fecha_hasta'):
        qs_usuarios = qs_usuarios.filter(fecha_registro__lte=fecha_fin(filtros['fecha_hasta']))
    if filtros.get('tipo_usuario'):
        qs_usuarios = qs_usuarios.filter(tipo_usuario=filtros['tipo_usuario'])
    if filtros.get('estado_cuenta'):
        qs_usuarios = qs_usuarios.filter(estado_cuenta=filtros['estado_cuenta'])

    # ── Base queryset perfiles profesionales ──────────────────
    from usuarios.models import PerfilProfesional
    qs_perfiles = PerfilProfesional.objects.all()
    if filtros.get('tipo_servicio'):
        qs_perfiles = qs_perfiles.filter(servicio=filtros['tipo_servicio'])
    if filtros.get('estado_cuenta'):
        qs_perfiles = qs_perfiles.filter(usuario__estado_cuenta=filtros['estado_cuenta'])
    if filtros.get('fecha_desde'):
        qs_perfiles = qs_perfiles.filter(usuario__fecha_registro__gte=fecha_inicio(filtros['fecha_desde']))
    if filtros.get('fecha_hasta'):
        qs_perfiles = qs_perfiles.filter(usuario__fecha_registro__lte=fecha_fin(filtros['fecha_hasta']))

    # ── Base queryset servicios ───────────────────────────────
    qs_servicios = Servicio.objects.all()
    if filtros.get('ciudad'):
        qs_servicios = qs_servicios.filter(ciudad__icontains=filtros['ciudad'])
    if filtros.get('tipo_servicio'):
        qs_servicios = qs_servicios.filter(categoria=filtros['tipo_servicio'])
    if filtros.get('fecha_desde'):
        qs_servicios = qs_servicios.filter(fecha_creacion__gte=fecha_inicio(filtros['fecha_desde']))
    if filtros.get('fecha_hasta'):
        qs_servicios = qs_servicios.filter(fecha_creacion__lte=fecha_fin(filtros['fecha_hasta']))

    datos = {
        'generado_el':    timezone.now().strftime('%d/%m/%Y %H:%M'),
        'total_usuarios': qs_usuarios.count(),
        'clientes':       qs_usuarios.filter(tipo_usuario='cliente').count(),
        'profesionales':  qs_usuarios.filter(tipo_usuario='profesional').count(),
        'aprobados':      qs_usuarios.filter(estado_cuenta='aprobado').count(),
        'pendientes':     qs_usuarios.filter(estado_cuenta='pendiente').count(),
        'rechazados':     qs_usuarios.filter(estado_cuenta='rechazado').count(),
        'sin_activar':    qs_usuarios.filter(activo=False).count(),
    }

    if tipo in ('profesionales', 'general'):
        datos['servicios'] = list(
            qs_perfiles.values('servicio').annotate(total=Count('servicio')).order_by('-total')
        )
        if filtros.get('ciudad'):
            prof_ids = qs_servicios.values_list('aplicaciones__profesional_id', flat=True).distinct()
            datos['profesionales_en_ciudad'] = qs_usuarios.filter(
                tipo_usuario='profesional', id_usuario__in=prof_ids
            ).count()

    if tipo in ('usuarios', 'general'):
        if filtros.get('fecha_desde') and filtros.get('fecha_hasta'):
            try:
                inicio = datetime.strptime(filtros['fecha_desde'], '%Y-%m-%d').date()
                fin    = datetime.strptime(filtros['fecha_hasta'], '%Y-%m-%d').date()
            except ValueError:
                inicio, fin = hoy - timedelta(days=29), hoy
        else:
            inicio, fin = hoy - timedelta(days=29), hoy

        delta = (fin - inicio).days + 1
        registros = []
        for i in range(delta):
            dia = inicio + timedelta(days=i)
            registros.append({
                'dia':      dia.strftime('%d/%m'),
                'cantidad': qs_usuarios.filter(
                    fecha_registro__gte=localizar(datetime(dia.year, dia.month, dia.day, 0, 0, 0)),
                    fecha_registro__lte=localizar(datetime(dia.year, dia.month, dia.day, 23, 59, 59)),
                ).count()
            })
        datos['registros_30_dias'] = registros

    if tipo == 'pendientes':
        qs_pend = qs_usuarios.filter(estado_cuenta='pendiente', activo=True)
        datos['lista_pendientes'] = list(
            qs_pend.values('nombre', 'apellido', 'correo', 'tipo_usuario', 'fecha_registro')
        )

    return datos


@admin_requerido
def admin_reporte_detalle(request, reporte_id, admin):
    reporte = get_object_or_404(ReporteAdmin, pk=reporte_id)
    try:
        datos = json.loads(reporte.datos_json) if reporte.datos_json else {}
    except json.JSONDecodeError:
        datos = {}
    return render(request, 'usuarios/admin/reporte_detalle.html', {
        'admin': admin, 'reporte': reporte, 'datos': datos,
        'datos_json': json.dumps(datos, ensure_ascii=False),
    })


@admin_requerido
def admin_eliminar_reporte(request, reporte_id, admin):
    reporte = get_object_or_404(ReporteAdmin, pk=reporte_id)
    titulo = reporte.titulo
    reporte.delete()
    messages.success(request, f'Reporte "{titulo}" eliminado.')
    return redirect('usuarios:admin_reportes')


# ─────────────────────────────────────────────────────────────
# DESCARGAR REPORTE EN PDF
# ─────────────────────────────────────────────────────────────

@admin_requerido
def admin_descargar_reporte_pdf(request, reporte_id, admin):
    try:
        from reportlab.lib.pagesizes import A4, letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        messages.error(request, 'La librería reportlab no está instalada. Ejecuta: pip install reportlab')
        return redirect('usuarios:admin_reporte_detalle', reporte_id=reporte_id)

    reporte = get_object_or_404(ReporteAdmin, pk=reporte_id)
    try:
        datos = json.loads(reporte.datos_json) if reporte.datos_json else {}
    except json.JSONDecodeError:
        datos = {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=reporte.titulo,
    )

    # ── Estilos ──────────────────────────────────────────────
    COLOR_GOLD   = colors.HexColor('#C9A84C')
    COLOR_DARK   = colors.HexColor('#1A1A18')
    COLOR_MUTED  = colors.HexColor('#7A7468')
    COLOR_GREEN  = colors.HexColor('#4EC994')
    COLOR_ORANGE = colors.HexColor('#D4903A')
    COLOR_RED    = colors.HexColor('#E05252')
    COLOR_BLUE   = colors.HexColor('#8EC1E8')
    COLOR_GRAY   = colors.HexColor('#2A2A28')

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TituloReporte',
        parent=styles['Title'],
        fontSize=22,
        textColor=COLOR_GOLD,
        spaceAfter=4,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        'Subtitulo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_MUTED,
        spaceAfter=2,
        fontName='Helvetica',
    )
    section_style = ParagraphStyle(
        'Seccion',
        parent=styles['Normal'],
        fontSize=12,
        textColor=COLOR_GOLD,
        spaceBefore=14,
        spaceAfter=6,
        fontName='Helvetica-Bold',
    )
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLOR_MUTED,
        fontName='Helvetica',
    )
    value_style = ParagraphStyle(
        'Valor',
        parent=styles['Normal'],
        fontSize=18,
        textColor=colors.white,
        fontName='Helvetica-Bold',
    )
    body_style = ParagraphStyle(
        'Cuerpo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#B0A898'),
        fontName='Helvetica',
        leading=14,
    )
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLOR_MUTED,
        fontName='Helvetica',
        alignment=TA_CENTER,
    )

    elements = []

    # ── Encabezado ───────────────────────────────────────────
    elements.append(Paragraph("HOME+", title_style))
    elements.append(Paragraph(reporte.titulo, ParagraphStyle(
        'TituloDoc', parent=styles['Normal'], fontSize=16,
        textColor=colors.white, fontName='Helvetica-Bold', spaceAfter=4,
    )))

    fecha_str = reporte.fecha_creacion.strftime('%d/%m/%Y a las %H:%M')
    creador   = reporte.creado_por.nombre if reporte.creado_por else 'Sistema'
    tipo_lbl  = dict(reporte._meta.get_field('tipo').choices).get(reporte.tipo, reporte.tipo) if hasattr(reporte._meta.get_field('tipo'), 'choices') else reporte.tipo
    elements.append(Paragraph(f"Tipo: {reporte.get_tipo_display()} &nbsp;·&nbsp; Generado el {fecha_str} por {creador}", subtitle_style))

    if reporte.descripcion:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(reporte.descripcion, body_style))

    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=COLOR_GOLD, spaceAfter=12))

    # ── Filtros aplicados ─────────────────────────────────────
    filtros = datos.get('filtros_aplicados', {})
    if filtros:
        LABELS = {
            'fecha_desde':   'Desde',
            'fecha_hasta':   'Hasta',
            'tipo_usuario':  'Tipo de usuario',
            'estado_cuenta': 'Estado',
            'tipo_servicio': 'Tipo de servicio',
            'ciudad':        'Ciudad',
        }
        partes = '   '.join(f"<b>{LABELS.get(k, k)}:</b> {v}" for k, v in filtros.items())
        elements.append(Paragraph(
            f"🔍 Filtros aplicados: &nbsp; {partes}",
            ParagraphStyle('Filtros', parent=styles['Normal'], fontSize=8,
                           textColor=COLOR_GOLD, fontName='Helvetica', spaceAfter=12,
                           backColor=colors.HexColor('#1A1610'), borderPadding=6)
        ))
        elements.append(Spacer(1, 4))

    # ── Estadísticas generales ────────────────────────────────
    elements.append(Paragraph("Estadísticas Generales", section_style))

    stat_data = [
        [
            _stat_cell("👥 Total Usuarios",  datos.get('total_usuarios', 0),  colors.white,   styles),
            _stat_cell("🏠 Clientes",         datos.get('clientes', 0),        COLOR_BLUE,     styles),
            _stat_cell("🔧 Profesionales",    datos.get('profesionales', 0),   COLOR_GOLD,     styles),
            _stat_cell("⏳ Pendientes",        datos.get('pendientes', 0),      COLOR_ORANGE,   styles),
        ],
        [
            _stat_cell("✅ Aprobados",         datos.get('aprobados', 0),       COLOR_GREEN,    styles),
            _stat_cell("❌ Rechazados",        datos.get('rechazados', 0),      COLOR_RED,      styles),
            _stat_cell("🔒 Sin activar",       datos.get('sin_activar', 0),     COLOR_MUTED,    styles),
            Paragraph("", styles['Normal']),
        ],
    ]

    stat_table = Table(stat_data, colWidths=[4.1*cm]*4, rowHeights=[2.2*cm, 2.2*cm])
    stat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), COLOR_GRAY),
        ('ROWBACKGROUND', (0,0), (-1,-1), COLOR_GRAY),
        ('BOX', (0,0), (-1,-1), 0.5, COLOR_GOLD),
        ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#3A3A38')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(stat_table)

    # ── Distribución de servicios ─────────────────────────────
    servicios = datos.get('servicios')
    if servicios:
        elements.append(Paragraph("Distribución de Servicios Profesionales", section_style))
        svc_header = [
            Paragraph("<b>Servicio</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold')),
            Paragraph("<b>Profesionales</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        ]
        svc_rows = [svc_header]
        for s in servicios:
            svc_rows.append([
                Paragraph(str(s.get('servicio', '')), body_style),
                Paragraph(str(s.get('total', 0)), ParagraphStyle('TDR', parent=body_style, alignment=TA_RIGHT)),
            ])
        svc_table = Table(svc_rows, colWidths=[12*cm, 4*cm])
        svc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#222220')),
            ('ROWBACKGROUND', (0,1), (-1,-1), [COLOR_GRAY, colors.HexColor('#232321')]),
            ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#3A3A38')),
            ('BOX', (0,0), (-1,-1), 0.5, COLOR_GOLD),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(svc_table)

    # ── Lista de pendientes ───────────────────────────────────
    pendientes = datos.get('lista_pendientes')
    if pendientes:
        elements.append(Paragraph("Lista de Cuentas Pendientes", section_style))
        pend_header = [
            Paragraph("<b>Nombre</b>",     ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold')),
            Paragraph("<b>Correo</b>",     ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold')),
            Paragraph("<b>Tipo</b>",       ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold')),
            Paragraph("<b>Registrado</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=9, textColor=COLOR_GOLD, fontName='Helvetica-Bold')),
        ]
        pend_rows = [pend_header]
        for p in pendientes:
            nombre   = f"{p.get('nombre','')} {p.get('apellido','')}".strip()
            correo   = str(p.get('correo', ''))
            tipo     = str(p.get('tipo_usuario', '')).capitalize()
            fecha    = str(p.get('fecha_registro', ''))[:10]
            pend_rows.append([
                Paragraph(nombre, body_style),
                Paragraph(correo, body_style),
                Paragraph(tipo,   body_style),
                Paragraph(fecha,  body_style),
            ])
        pend_table = Table(pend_rows, colWidths=[4.5*cm, 5.5*cm, 2.5*cm, 3.5*cm])
        pend_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#222220')),
            ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#3A3A38')),
            ('BOX', (0,0), (-1,-1), 0.5, COLOR_GOLD),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        elements.append(pend_table)

    # ── Registros 30 días ─────────────────────────────────────
    registros = datos.get('registros_30_dias')
    if registros:
        elements.append(Paragraph("Registros Últimos 30 Días", section_style))
        # Tabla compacta de 6 columnas
        dias_chunk = [registros[i:i+6] for i in range(0, len(registros), 6)]
        for chunk in dias_chunk:
            header_row = [Paragraph(f"<b>{d['dia']}</b>", ParagraphStyle('TH', parent=styles['Normal'], fontSize=8, textColor=COLOR_GOLD, fontName='Helvetica-Bold', alignment=TA_CENTER)) for d in chunk]
            value_row  = [Paragraph(str(d['cantidad']), ParagraphStyle('TV', parent=styles['Normal'], fontSize=10, textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_CENTER)) for d in chunk]
            # pad to 6 cols
            while len(header_row) < 6:
                header_row.append(Paragraph("", styles['Normal']))
                value_row.append(Paragraph("", styles['Normal']))
            reg_table = Table([header_row, value_row], colWidths=[2.7*cm]*6)
            reg_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), COLOR_GRAY),
                ('INNERGRID', (0,0), (-1,-1), 0.3, colors.HexColor('#3A3A38')),
                ('BOX', (0,0), (-1,-1), 0.5, COLOR_GOLD),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ]))
            elements.append(reg_table)
            elements.append(Spacer(1, 4))

    # ── Footer ────────────────────────────────────────────────
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_MUTED, spaceAfter=8))
    elements.append(Paragraph(
        f"HOME+ &nbsp;·&nbsp; Reporte generado el {fecha_str} &nbsp;·&nbsp; Panel de Administración",
        footer_style,
    ))

    doc.build(elements)
    buffer.seek(0)

    nombre_archivo = reporte.titulo.replace(' ', '_').replace('/', '-')
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}.pdf"'
    return response


def _stat_cell(label, value, color, styles):
    """Crea una celda de estadística: valor grande + etiqueta pequeña."""
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph
    from reportlab.lib.enums import TA_CENTER

    lbl_style = ParagraphStyle(
        'SL', parent=styles['Normal'], fontSize=8,
        textColor=colors.HexColor('#7A7468'), fontName='Helvetica',
        alignment=TA_CENTER, leading=10, spaceAfter=0, spaceBefore=2,
    )
    val_style = ParagraphStyle(
        'SV', parent=styles['Normal'], fontSize=22,
        textColor=color, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=26, spaceAfter=0, spaceBefore=0,
    )
    # Una lista de flowables es válida como contenido de celda en ReportLab
    return [Paragraph(str(value), val_style), Paragraph(label, lbl_style)]
