import re
from pypdf import PdfReader
from datetime import datetime

def extraer_datos_factura_pdf(stream_pdf):
    reader = PdfReader(stream_pdf)
    texto = ""
    for page in reader.pages:
        texto += page.extract_text() + "\n"
        
    datos = {
        "num_factura": "",
        "cliente": "",
        "fecha": "",
        "pais": "",
        "moneda": "USD ($)",
        "monto_neto": 0.0,
        "monto_iva": 0.0,
        "monto_total": 0.0
    }
    
    # 1. HONDURAS (Detección por CAI o RTN 0508)
    if "CAI" in texto or "RTN 05081975001517" in texto:
        datos["pais"] = "Honduras"
        datos["moneda"] = "HNL (L)"
        
        # N° Factura
        match_fac = re.search(r'FACTURA\s*\n?\s*(\d{3}-\d{3}-\d{2}-\d{8})', texto)
        if match_fac:
            datos["num_factura"] = match_fac.group(1)
            
        # Cliente
        match_cli = re.search(r'Cliente:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).split("Dirección:")[0].strip()
            
        # Fecha
        match_fec = re.search(r'Fecha:\s*(\d{2}\s+de\s+\w+\s+de\s+\d{4})', texto)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        # Total
        match_tot = re.search(r'Total a Pagar L\.\s*L?\s*([\d,]+\.\d{2})', texto)
        if match_tot:
            datos["monto_total"] = float(match_tot.group(1).replace(',', ''))
            
        # ISV
        match_isv = re.search(r'15%\s*I\.S\.V\.\s*L\.\s*L?\s*([\d,]+\.\d{2})', texto)
        if match_isv:
            datos["monto_iva"] = float(match_isv.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 2. GUATEMALA (Detección por FEL / SAT / NIT Emisor)
    elif "NIT Emisor:" in texto or "Número de DTE:" in texto:
        datos["pais"] = "Guatemala"
        
        # Moneda
        if "Moneda: GTQ" in texto:
            datos["moneda"] = "GTQ (Q)"
        else:
            datos["moneda"] = "USD ($)"
            
        # N° Factura / DTE
        match_dte = re.search(r'Número de DTE:\s*(\d+)', texto)
        if match_dte:
            datos["num_factura"] = match_dte.group(1)
            
        # Cliente
        match_cli = re.search(r'Nombre Receptor:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).strip()
            
        # Fecha
        match_fec = re.search(r'Fecha y hora de emision:\s*(\d{2}-\w+-\d{4})', texto)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        # Total
        match_tot = re.search(r'TOTALES:\s*[\d\.,]+\s*[\d\.,]+\s*([\d,]+\.\d{2})', texto)
        if not match_tot:
            match_tot = re.search(r'([\d,]+\.\d{2})\s*IVA', texto)
        if match_tot:
            datos["monto_total"] = float(match_tot.group(1).replace(',', ''))
            
        # IVA
        match_iva = re.search(r'IVA\s*([\d,]+\.\d{2})', texto)
        if match_iva:
            datos["monto_iva"] = float(match_iva.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 3. COSTA RICA (Detección por Clave / Consecutivo / Cédula 3-101)
    elif "Consecutivo:" in texto or "Clave:" in texto:
        datos["pais"] = "Costa Rica"
        datos["moneda"] = "USD ($)"
        
        # Consecutivo / Factura
        match_cons = re.search(r'Consecutivo:\s*(\d+)', texto)
        if match_cons:
            datos["num_factura"] = match_cons.group(1)
            
        # Cliente
        match_cli = re.search(r'Nombre:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).strip()
            
        # Fecha
        match_fec = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', texto)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        # Total
        match_tot = re.search(r'Total:\s*([\d\.,]+)', texto)
        if match_tot:
            valor_str = match_tot.group(1).replace('.', '').replace(',', '.')
            datos["monto_total"] = float(valor_str)
            
        # IVA
        match_iva = re.search(r'I\.V\.A\s*([\d\.,]+)', texto)
        if match_iva:
            valor_iva = match_iva.group(1).replace('.', '').replace(',', '.')
            datos["monto_iva"] = float(valor_iva)
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    return datos