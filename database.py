import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional

class CafeDatabase:
    def __init__(self, db_path='cafe_de_quito.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa la base de datos con las tablas necesarias"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabla de pedidos
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_cliente TEXT NOT NULL,
                    items TEXT NOT NULL,  -- JSON string con los items
                    total REAL NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'pendiente',
                    fecha_creacion TEXT NOT NULL,
                    fecha_despacho TEXT
                )
            ''')
            
            # Tabla de productos (para futuras expansiones)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    precio REAL NOT NULL
                )
            ''')
            
            # Insertar productos por defecto si no existen
            cursor.execute('SELECT COUNT(*) FROM productos')
            if cursor.fetchone()[0] == 0:
                productos_default = [
                    (1, "Café Americano", 1.50),
                    (2, "Café Expresso", 1.50),
                    (3, "Cappuccino", 2)
                ]
                cursor.executemany(
                    'INSERT INTO productos (id, nombre, precio) VALUES (?, ?, ?)',
                    productos_default
                )
            
            conn.commit()
    
    def crear_pedido(self, nombre_cliente: str, items: List[Dict], total: float) -> int:
        """Crea un nuevo pedido y retorna su ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            fecha_creacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            items_json = json.dumps(items)
            
            cursor.execute('''
                INSERT INTO pedidos (nombre_cliente, items, total, estado, fecha_creacion)
                VALUES (?, ?, ?, 'pendiente', ?)
            ''', (nombre_cliente, items_json, total, fecha_creacion))
            
            pedido_id = cursor.lastrowid
            conn.commit()
            
            return pedido_id
    
    def obtener_pedidos(self) -> List[Dict]:
        """Obtiene todos los pedidos"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, nombre_cliente, items, total, estado, fecha_creacion, fecha_despacho
                FROM pedidos ORDER BY id DESC
            ''')
            
            pedidos = []
            for row in cursor.fetchall():
                pedido = {
                    'id': row[0],
                    'nombre_cliente': row[1],
                    'items': json.loads(row[2]),
                    'total': row[3],
                    'estado': row[4],
                    'fecha_creacion': row[5],
                    'fecha_despacho': row[6]
                }
                pedidos.append(pedido)
            
            return pedidos
    
    def despachar_pedido(self, pedido_id: int) -> bool:
        """Marca un pedido como despachado"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            fecha_despacho = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                UPDATE pedidos 
                SET estado = 'despachado', fecha_despacho = ?
                WHERE id = ? AND estado = 'pendiente'
            ''', (fecha_despacho, pedido_id))
            
            rows_affected = cursor.rowcount
            conn.commit()
            
            return rows_affected > 0
    
    def obtener_pedido_por_id(self, pedido_id: int) -> Optional[Dict]:
        """Obtiene un pedido específico por ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, nombre_cliente, items, total, estado, fecha_creacion, fecha_despacho
                FROM pedidos WHERE id = ?
            ''', (pedido_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'nombre_cliente': row[1],
                    'items': json.loads(row[2]),
                    'total': row[3],
                    'estado': row[4],
                    'fecha_creacion': row[5],
                    'fecha_despacho': row[6]
                }
            
            return None
    
    def obtener_productos(self) -> Dict[int, Dict]:
        """Obtiene todos los productos"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, nombre, precio FROM productos')
            
            productos = {}
            for row in cursor.fetchall():
                productos[row[0]] = {
                    'nombre': row[1],
                    'precio': row[2]
                }
            
            return productos
    
    def obtener_estadisticas(self) -> Dict:
        """Calcula y retorna estadísticas de los pedidos"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Estadísticas básicas
            cursor.execute('SELECT COUNT(*) FROM pedidos')
            total_pedidos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE estado = 'pendiente'")
            pedidos_pendientes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE estado = 'despachado'")
            pedidos_despachados = cursor.fetchone()[0]
            
            # Ingresos totales
            cursor.execute("SELECT COALESCE(SUM(total), 0) FROM pedidos WHERE estado = 'despachado'")
            ingresos_totales = cursor.fetchone()[0]
            
            # Producto más vendido
            cursor.execute("SELECT items FROM pedidos WHERE estado = 'despachado'")
            ventas_por_producto = {}
            
            for row in cursor.fetchall():
                items = json.loads(row[0])
                for item in items:
                    nombre = item['nombre']
                    cantidad = item['cantidad']
                    
                    if nombre in ventas_por_producto:
                        ventas_por_producto[nombre] += cantidad
                    else:
                        ventas_por_producto[nombre] = cantidad
            
            producto_mas_vendido = ("Ninguno", 0)
            if ventas_por_producto:
                producto_mas_vendido = max(ventas_por_producto.items(), key=lambda x: x[1])
            
            return {
                'total_pedidos': total_pedidos,
                'pedidos_pendientes': pedidos_pendientes,
                'pedidos_despachados': pedidos_despachados,
                'ingresos_totales': ingresos_totales,
                'producto_mas_vendido': {
                    'nombre': producto_mas_vendido[0],
                    'cantidad': producto_mas_vendido[1]
                }
            }