import sqlite3

DB_NAME = "ventas_cobros.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabla de Ventas / Facturas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            num_factura TEXT UNIQUE NOT NULL,
            cliente TEXT NOT NULL,
            fecha TEXT NOT NULL,
            monto_total REAL NOT NULL,
            saldo_pendiente REAL NOT NULL,
            estado TEXT NOT NULL
        )
    ''')
    
    # Tabla de Abonos / Pagos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS abonos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            monto REAL NOT NULL,
            metodo_pago TEXT NOT NULL,
            referencia TEXT,
            FOREIGN KEY (venta_id) REFERENCES ventas (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def obtener_ventas():
    conn = sqlite3.connect(DB_NAME)
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM ventas ORDER BY id DESC", conn)
    conn.close()
    return df

def obtener_abonos():
    conn = sqlite3.connect(DB_NAME)
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM abonos ORDER BY id DESC", conn)
    conn.close()
    return df

def registrar_venta(num_factura, cliente, fecha, monto_total):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO ventas (num_factura, cliente, fecha, monto_total, saldo_pendiente, estado)
            VALUES (?, ?, ?, ?, ?, 'Pendiente')
        ''', (num_factura, cliente, str(fecha), monto_total, monto_total))
        conn.commit()
        return True, "Venta registrada con éxito."
    except sqlite3.IntegrityError:
        return False, f"El número de factura '{num_factura}' ya existe."
    finally:
        conn.close()

def registrar_abono(venta_id, fecha, monto, metodo_pago, referencia):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Consultar venta
    cursor.execute("SELECT saldo_pendiente, monto_total FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    
    if not venta:
        conn.close()
        return False, "Factura no encontrada."
        
    saldo_actual, monto_total = venta
    
    if monto > saldo_actual:
        conn.close()
        return False, f"El abono (${monto:.2f}) excede el saldo pendiente (${saldo_actual:.2f})."
    
    nuevo_saldo = saldo_actual - monto
    nuevo_estado = "Pagado" if nuevo_saldo == 0 else "Parcial"
    
    # Insertar abono
    cursor.execute('''
        INSERT INTO abonos (venta_id, fecha, monto, metodo_pago, referencia)
        VALUES (?, ?, ?, ?, ?)
    ''', (venta_id, str(fecha), monto, metodo_pago, referencia))
    
    # Actualizar venta
    cursor.execute('''
        UPDATE ventas 
        SET saldo_pendiente = ?, estado = ?
        WHERE id = ?
    ''', (nuevo_saldo, nuevo_estado, venta_id))
    
    conn.commit()
    conn.close()
    return True, "Abono aplicado exitosamente."