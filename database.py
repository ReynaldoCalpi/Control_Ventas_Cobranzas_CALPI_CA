import sqlite3
import pandas as pd

DB_NAME = "ventas_cobros.db"

# Tasas de IVA / ISV por país
TASAS_IVA = {
    "El Salvador": 0.13,
    "Guatemala": 0.12,
    "Honduras": 0.15,
    "Nicaragua": 0.15,
    "Costa Rica": 0.13
}

# Monedas permitidas por país
MONEDAS_POR_PAIS = {
    "El Salvador": ["USD ($)"],
    "Guatemala": ["GTQ (Q)", "USD ($)"],
    "Honduras": ["HNL (L)"],
    "Nicaragua": ["USD ($)"],
    "Costa Rica": ["USD ($)"]
}

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
            pais TEXT NOT NULL,
            moneda TEXT NOT NULL,
            monto_neto REAL NOT NULL,
            monto_iva REAL NOT NULL,
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

def obtener_ventas(pais=None, moneda=None):
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT * FROM ventas"
    params = []
    conditions = []
    
    if pais and pais != "Todos":
        conditions.append("pais = ?")
        params.append(pais)
    if moneda and moneda != "Todas":
        conditions.append("moneda = ?")
        params.append(moneda)
        
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY id DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def obtener_abonos():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM abonos ORDER BY id DESC", conn)
    conn.close()
    return df

def calcular_desglose_iva(monto_total, pais):
    tasa = TASAS_IVA.get(pais, 0.13)
    neto = round(monto_total / (1 + tasa), 2)
    iva = round(monto_total - neto, 2)
    return neto, iva

def registrar_venta(num_factura, cliente, fecha, pais, moneda, monto_total, monto_neto=None, monto_iva=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if monto_neto is None or monto_iva is None:
        monto_neto, monto_iva = calcular_desglose_iva(monto_total, pais)
        
    try:
        cursor.execute('''
            INSERT INTO ventas (num_factura, cliente, fecha, pais, moneda, monto_neto, monto_iva, monto_total, saldo_pendiente, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente')
        ''', (num_factura, cliente, str(fecha), pais, moneda, monto_neto, monto_iva, monto_total, monto_total))
        conn.commit()
        return True, "Venta registrada con éxito."
    except sqlite3.IntegrityError:
        return False, f"El número de factura '{num_factura}' ya existe."
    finally:
        conn.close()

def registrar_ventas_masivas(df_ventas):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    exitosos = 0
    errores = []
    
    for idx, row in df_ventas.iterrows():
        num_factura = str(row['num_factura']).strip() if pd.notnull(row['num_factura']) else ""
        cliente = str(row['cliente']).strip() if pd.notnull(row['cliente']) else ""
        fecha = str(row['fecha']).strip() if pd.notnull(row['fecha']) else ""
        pais = str(row['pais']).strip() if pd.notnull(row['pais']) else "El Salvador"
        moneda = str(row['moneda']).strip() if pd.notnull(row['moneda']) else "USD ($)"
        
        try:
            monto_total = float(row['monto_total'])
        except (ValueError, TypeError):
            errores.append(f"Fila {idx+1}: Monto total inválido para factura '{num_factura}'.")
            continue

        if not num_factura or not cliente:
            errores.append(f"Fila {idx+1}: Faltan datos requeridos (Número de Factura o Cliente).")
            continue
            
        monto_neto = float(row['monto_neto']) if 'monto_neto' in row and pd.notnull(row['monto_neto']) else None
        monto_iva = float(row['monto_iva']) if 'monto_iva' in row and pd.notnull(row['monto_iva']) else None
        
        if monto_neto is None or monto_iva is None:
            monto_neto, monto_iva = calcular_desglose_iva(monto_total, pais)
            
        try:
            cursor.execute('''
                INSERT INTO ventas (num_factura, cliente, fecha, pais, moneda, monto_neto, monto_iva, monto_total, saldo_pendiente, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente')
            ''', (num_factura, cliente, fecha, pais, moneda, monto_neto, monto_iva, monto_total, monto_total))
            exitosos += 1
        except sqlite3.IntegrityError:
            errores.append(f"La factura '{num_factura}' ya existe en el sistema.")
        except Exception as e:
            errores.append(f"Error en factura '{num_factura}': {str(e)}")
            
    conn.commit()
    conn.close()
    return exitosos, errores

def registrar_abono(venta_id, fecha, monto, metodo_pago, referencia):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT saldo_pendiente, monto_total FROM ventas WHERE id = ?", (venta_id,))
    venta = cursor.fetchone()
    
    if not venta:
        conn.close()
        return False, "Factura no encontrada."
        
    saldo_actual, monto_total = venta
    
    if round(monto, 2) > round(saldo_actual, 2):
        conn.close()
        return False, f"El abono ({monto:.2f}) excede el saldo pendiente ({saldo_actual:.2f})."
    
    nuevo_saldo = round(saldo_actual - monto, 2)
    nuevo_estado = "Pagado" if nuevo_saldo == 0 else "Parcial"
    
    cursor.execute('''
        INSERT INTO abonos (venta_id, fecha, monto, metodo_pago, referencia)
        VALUES (?, ?, ?, ?, ?)
    ''', (venta_id, str(fecha), monto, metodo_pago, referencia))
    
    cursor.execute('''
        UPDATE ventas 
        SET saldo_pendiente = ?, estado = ?
        WHERE id = ?
    ''', (nuevo_saldo, nuevo_estado, venta_id))
    
    conn.commit()
    conn.close()
    return True, "Abono aplicado exitosamente."
