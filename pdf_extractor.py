import re
from pypdf import PdfReader

def extraer_datos_factura_pdf(stream_pdf, filename=""):
    try:
        reader = PdfReader(stream_pdf)
        texto = ""
        for page in reader.pages:
            texto_pag = page.extract_text()
            if texto_pag:
                texto += texto_pag + "\n"
    except Exception as e:
        return {
            "num_factura": f"ERR-{filename}",
            "cliente": "Error al leer PDF",
            "fecha": "",
            "pais": "Desconocido",
            "moneda": "USD ($)",
            "monto_neto": 0.0,
            "monto_iva": 0.0,
            "monto_total": 0.0
        }
        
    datos = {
        "num_factura": "",
        "cliente": "",
        "fecha": "",
        "pais": "El Salvador",
        "moneda": "USD ($)",
        "monto_neto": 0.0,
        "monto_iva": 0.0,
        "monto_total": 0.0
    }
    
    # 1. HONDURAS (Detección por CAI, RTN o Lempiras)
    if "CAI" in texto or "05081975001517" in texto or "LEMPIRAS" in texto.upper() or "RTN" in texto:
        datos["pais"] = "Honduras"
        datos["moneda"] = "HNL (L)"
        
        # N° Factura (Ej: 000-002-01-00000828)
        match_fac = re.search(r'000-\d{3}-\d{2}-\d{8}', texto)
        if not match_fac:
            match_fac = re.search(r'FACTURA\s*\n?\s*([0-9\-]+)', texto, re.IGNORECASE)
        if match_fac:
            datos["num_factura"] = match_fac.group(0 if match_fac.group(0).startswith("000") else 1)
            
        # Cliente
        match_cli = re.search(r'Cliente:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).split("Dirección:")[0].split("R.TN")[0].strip()
            
        # Fecha (Ej: 06 de octubre de 2026)
        match_fec = re.search(r'Fecha:\s*(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', texto, re.IGNORECASE)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        # Total
        match_tot = re.search(r'Total a Pagar L\.\s*L?\s*([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if match_tot:
            datos["monto_total"] = float(match_tot.group(1).replace(',', ''))
            
        # ISV (15%)
        match_isv = re.search(r'15%\s*I\.S\.V\.\s*L\.\s*L?\s*([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if match_isv:
            datos["monto_iva"] = float(match_isv.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 2. GUATEMALA (Detección por FEL / SAT / NIT / DTE)
    elif "NIT Emisor:" in texto or "Número de DTE:" in texto or "GUATEMALA" in texto.upper():
        datos["pais"] = "Guatemala"
        
        if "Moneda: GTQ" in texto or " Q " in texto or "(Q)" in texto:
            datos["moneda"] = "GTQ (Q)"
        else:
            datos["moneda"] = "USD ($)"
            
        # N° Factura / DTE
        match_dte = re.search(r'Número de DTE:\s*(\d+)', texto)
        if match_dte:
            datos["num_factura"] = match_dte.group(1)
        else:
            match_serie = re.search(r'Serie:\s*([A-Z0-9]+)', texto)
            if match_serie:
                datos["num_factura"] = match_serie.group(1)
            
        # Cliente
        match_cli = re.search(r'Nombre Receptor:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).strip()
            
        # Fecha
        match_fec = re.search(r'Fecha y hora de emision:\s*(\d{2}-\w+-\d{4})', texto, re.IGNORECASE)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        # Total
        match_tot = re.search(r'TOTALES:\s*[\d\.,]+\s*[\d\.,]+\s*([\d,]+\.\d{2})', texto)
        if match_tot:
            datos["monto_total"] = float(match_tot.group(1).replace(',', ''))
            
        # IVA
        match_iva = re.search(r'IVA\s*([\d,]+\.\d{2})', texto)
        if match_iva:
            datos["monto_iva"] = float(match_iva.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 3. COSTA RICA (Detección por Consecutivo / Clave / Cédula 3-101)
    elif "Consecutivo:" in texto or "Clave:" in texto or "COSTA RICA" in texto.upper():
        datos["pais"] = "Costa Rica"
        datos["moneda"] = "USD ($)"
        
        match_cons = re.search(r'Consecutivo:\s*(\d+)', texto)
        if match_cons:
            datos["num_factura"] = match_cons.group(1)
            
        match_cli = re.search(r'Nombre:\s*(.+)', texto)
        if match_cli:
            datos["cliente"] = match_cli.group(1).strip()
            
        match_fec = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', texto)
        if match_fec:
            datos["fecha"] = match_fec.group(1)
            
        match_tot = re.search(r'Total:\s*([\d\.,]+)', texto)
        if match_tot:
            val_str = match_tot.group(1).replace('.', '').replace(',', '.')
            try:
                datos["monto_total"] = float(val_str)
            except ValueError:
                pass
                
        match_iva = re.search(r'I\.V\.A\s*([\d\.,]+)', texto)
        if match_iva:
            val_iva = match_iva.group(1).replace('.', '').replace(',', '.')
            try:
                datos["monto_iva"] = float(val_iva)
            except ValueError:
                pass
                
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    if not datos["num_factura"] and filename:
        datos["num_factura"] = filename.replace('.pdf', '')
        
    return datos
