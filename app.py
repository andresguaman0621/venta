from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from datetime import datetime
import json
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from database import CafeDatabase

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cafe_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Inicializar base de datos
db = CafeDatabase()

@app.route('/')
def index():
    productos = db.obtener_productos()
    return render_template('index.html', productos=productos)

@app.route('/monitor')
def monitor():
    return render_template('monitor.html')

@app.route('/despacho')
def despacho():
    return render_template('despacho.html')

@app.route('/estadisticas')
def estadisticas():
    return render_template('estadisticas.html')

@app.route('/api/crear_pedido', methods=['POST'])
def crear_pedido():
    data = request.get_json()
    nombre_cliente = data.get('nombre_cliente')
    productos_pedido = data.get('productos')
    
    # Obtener productos de la base de datos
    productos = db.obtener_productos()
    
    # Calcular total con precisión decimal
    from decimal import Decimal, ROUND_HALF_UP
    
    total = Decimal('0')
    items = []
    for producto_id, cantidad in productos_pedido.items():
        if cantidad > 0:
            producto = productos[int(producto_id)]
            precio = Decimal(str(producto['precio']))
            cantidad_decimal = Decimal(str(cantidad))
            subtotal = precio * cantidad_decimal
            total += subtotal
            items.append({
                'nombre': producto['nombre'],
                'cantidad': cantidad,
                'precio': float(precio),
                'subtotal': float(subtotal)
            })
    
    # Convertir total a float con precisión de 2 decimales
    total = float(total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    if not items:
        return jsonify({'error': 'No se seleccionaron productos'}), 400
    
    # Crear pedido en la base de datos
    pedido_id = db.crear_pedido(nombre_cliente, items, total)
    
    # Obtener el pedido completo de la base de datos
    pedido = db.obtener_pedido_por_id(pedido_id)
    
    # Emitir evento a todos los clientes conectados
    socketio.emit('nuevo_pedido', pedido)
    
    return jsonify({'success': True, 'pedido_id': pedido_id})

@app.route('/api/pedidos')
def obtener_pedidos():
    pedidos = db.obtener_pedidos()
    return jsonify(pedidos)

@app.route('/api/despachar_pedido/<int:pedido_id>', methods=['POST'])
def despachar_pedido(pedido_id):
    # Despachar pedido en la base de datos
    success = db.despachar_pedido(pedido_id)
    
    if success:
        # Obtener el pedido actualizado
        pedido = db.obtener_pedido_por_id(pedido_id)
        
        # Emitir evento de pedido despachado
        socketio.emit('pedido_despachado', pedido)
        
        return jsonify({'success': True})
    
    return jsonify({'error': 'Pedido no encontrado o ya despachado'}), 404

@app.route('/api/estadisticas')
def obtener_estadisticas():
    estadisticas = db.obtener_estadisticas()
    return jsonify(estadisticas)

def generar_reporte_pdf():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Obtener datos de la base de datos
    pedidos = db.obtener_pedidos()
    estadisticas = db.obtener_estadisticas()
    
    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.Color(0.27, 0.31, 0.14)  # Color café
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.Color(0.27, 0.31, 0.14)
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Contenido del documento
    story = []
    
    # Título
    story.append(Paragraph("REPORTE DE VENTAS - CAFÉ DE QUITO", title_style))
    story.append(Spacer(1, 12))
    
    # Información del reporte
    fecha_actual = datetime.now().strftime('%d de %B de %Y - %H:%M')
    story.append(Paragraph(f"<b>Fecha del reporte:</b> {fecha_actual}", normal_style))
    story.append(Spacer(1, 20))
    
    # Resumen ejecutivo
    story.append(Paragraph("RESUMEN EJECUTIVO", heading_style))
    
    total_pedidos = estadisticas['total_pedidos']
    pedidos_pendientes = estadisticas['pedidos_pendientes']
    pedidos_despachados = estadisticas['pedidos_despachados']
    ingresos_totales = estadisticas['ingresos_totales']
    
    # Tabla de resumen
    resumen_data = [
        ['Métrica', 'Valor'],
        ['Total de pedidos generados', str(total_pedidos)],
        ['Pedidos pendientes de despacho', str(pedidos_pendientes)],
        ['Pedidos despachados', str(pedidos_despachados)],
        ['Ingresos totales', f"${ingresos_totales:.2f}"],
    ]
    
    if pedidos_despachados > 0:
        promedio_venta = ingresos_totales / pedidos_despachados
        resumen_data.append(['Valor promedio por pedido', f"${promedio_venta:.2f}"])
    
    resumen_table = Table(resumen_data, colWidths=[3*inch, 2*inch])
    resumen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.27, 0.31, 0.14)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(resumen_table)
    story.append(Spacer(1, 20))
    
    # Análisis de productos
    story.append(Paragraph("ANÁLISIS DE PRODUCTOS", heading_style))
    
    ventas_por_producto = {}
    ingresos_por_producto = {}
    
    for pedido in pedidos:
        if pedido['estado'] == 'despachado':
            for item in pedido['items']:
                nombre = item['nombre']
                if nombre in ventas_por_producto:
                    ventas_por_producto[nombre] += item['cantidad']
                    ingresos_por_producto[nombre] += item['subtotal']
                else:
                    ventas_por_producto[nombre] = item['cantidad']
                    ingresos_por_producto[nombre] = item['subtotal']
    
    if ventas_por_producto:
        productos_data = [['Producto', 'Unidades Vendidas', 'Ingresos Generados']]
        for nombre, cantidad in sorted(ventas_por_producto.items(), key=lambda x: x[1], reverse=True):
            ingresos = ingresos_por_producto[nombre]
            productos_data.append([nombre, str(cantidad), f"${ingresos:.2f}"])
        
        productos_table = Table(productos_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        productos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.27, 0.31, 0.14)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(productos_table)
    else:
        story.append(Paragraph("No hay ventas registradas para mostrar análisis de productos.", normal_style))
    
    story.append(Spacer(1, 20))
    
    # Detalle de pedidos
    story.append(Paragraph("DETALLE DE PEDIDOS", heading_style))
    
    if pedidos:
        pedidos_data = [['ID', 'Cliente', 'Estado', 'Total', 'Fecha Creación']]
        
        for pedido in sorted(pedidos, key=lambda x: x['id']):
            estado_texto = "Pendiente" if pedido['estado'] == 'pendiente' else "Despachado"
            fecha = pedido['fecha_creacion'].split(' ')[0]  # Solo la fecha, sin hora
            pedidos_data.append([
                f"#{pedido['id']}",
                pedido['nombre_cliente'],
                estado_texto,
                f"${pedido['total']:.2f}",
                fecha
            ])
        
        pedidos_table = Table(pedidos_data, colWidths=[0.8*inch, 2*inch, 1.2*inch, 1*inch, 1.2*inch])
        pedidos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.27, 0.31, 0.14)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
        ]))
        
        story.append(pedidos_table)
    else:
        story.append(Paragraph("No hay pedidos registrados.", normal_style))
    
    story.append(Spacer(1, 20))
    
    # Pie de página
    story.append(Paragraph("Este reporte fue generado automáticamente por el sistema Café de Quito.", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, 
                          textColor=colors.grey, alignment=TA_CENTER)))
    
    # Generar PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/api/exportar_reporte_pdf')
def exportar_reporte_pdf():
    try:
        pdf_buffer = generar_reporte_pdf()
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'reporte-cafe-de-quito-{fecha_actual}.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print('Cliente conectado')

@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')

if __name__ == '__main__':
    import os
    # Obtener puerto de Railway o usar 5000 por defecto
    port = int(os.environ.get('PORT', 5000))
    # Para producción en Railway
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
else:
    # Para producción en cPanel
    application = app