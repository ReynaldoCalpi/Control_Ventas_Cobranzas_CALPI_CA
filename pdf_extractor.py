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
        
        # N° Factura (Une correlativos divididos en 2 líneas como 000-002-01-00000 + 828)
        m_fac_split = re.search(r'FACTURA[\s\|]*(\d{3}-\d{3}-\d{2}-\d{5})[\s\|]*(\d{3})', texto, re.IGNORECASE)
        if m_fac_split:
            datos["num_factura"] = f"{m_fac_split.group(1)}{m_fac_split.group(2)}"
        else:
            m_fac_dir = re.search(r'FACTURA[\s\|]*(\d{3}-\d{3}-\d{2}-\d{8})', texto, re.IGNORECASE)
            if m_fac_dir:
                datos["num_factura"] = m_fac_dir.group(1)
            else:
                m_fac_any = re.search(r'000-\d{3}-\d{2}-\d{8}', texto)
                if m_fac_any:
                    datos["num_factura"] = m_fac_any.group(0)
            
        # Cliente
        m_cli = re.search(r'Cliente:[\s\|]*(.+)', texto, re.IGNORECASE)
        if m_cli:
            cli_raw = m_cli.group(1).split("Dirección:")[0].split("R.TN")[0].split("RTN")[0].strip()
            datos["cliente"] = re.sub(r'^[\|:\s]+|[\|:\s]+$', '', cli_raw)
            
        # Fecha
        m_fec = re.search(r'Fecha:[\s\|]*(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', texto, re.IGNORECASE)
        if not m_fec:
            m_fec = re.search(r'Fecha:[\s\|]*(\d{2}/\d{2}/\d{4})', texto, re.IGNORECASE)
        if m_fec:
            datos["fecha"] = m_fec.group(1)
            
        # Total a Pagar
        m_tot = re.search(r'Total a Pagar L\.[\s\|]*L?\s*([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if m_tot:
            datos["monto_total"] = float(m_tot.group(1).replace(',', ''))
            
        # 15% ISV
        m_isv = re.search(r'15%\s*I\.S\.V\.\s*L\.[\s\|]*L?\s*([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if m_isv:
            datos["monto_iva"] = float(m_isv.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 2. GUATEMALA (Detección por FEL / SAT / NIT / DTE)
    elif "NIT Emisor:" in texto or "Número de DTE:" in texto or "GUATEMALA" in texto.upper():
        datos["pais"] = "Guatemala"
        
        if "Moneda: GTQ" in texto or " Q " in texto or "(Q)" in texto:
            datos["moneda"] = "GTQ (Q)"
        else:
            datos["moneda"] = "USD ($)"
            
        # N° Factura / DTE
        m_dte = re.search(r'Número de DTE:[\s\|]*(\d+)', texto)
        if m_dte:
            datos["num_factura"] = m_dte.group(1)
        else:
            m_serie = re.search(r'Serie:[\s\|]*([A-Z0-9]+)', texto)
            if m_serie:
                datos["num_factura"] = m_serie.group(1)
            
        # Cliente
        m_cli = re.search(r'Nombre Receptor:[\s\|]*(.+)', texto)
        if m_cli:
            cli_raw = m_cli.group(1).split("Factura")[0].split("Fecha")[0].strip()
            datos["cliente"] = re.sub(r'^[\|:\s]+|[\|:\s]+$', '', cli_raw)
            
        # Fecha
        m_fec = re.search(r'Fecha y hora de emision:[\s\|]*(\d{2}-\w+-\d{4})', texto, re.IGNORECASE)
        if m_fec:
            datos["fecha"] = m_fec.group(1)
            
        # Total
        m_tot = re.search(r'TOTALES:[\s\|]*[\d\.,]+[\s\|]*[\d\.,]+[\s\|]*([\d,]+\.\d{2})', texto)
        if m_tot:
            datos["monto_total"] = float(m_tot.group(1).replace(',', ''))
            
        # IVA
        m_iva = re.search(r'TOTALES:[\s\S]*?IVA[\s\|]*([\d,]+\.\d{2})', texto)
        if m_iva:
            datos["monto_iva"] = float(m_iva.group(1).replace(',', ''))
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # 3. COSTA RICA (Detección por Consecutivo / Clave / Cédula 3-101)
    elif "Consecutivo:" in texto or "Clave:" in texto or "COSTA RICA" in texto.upper():
        datos["pais"] = "Costa Rica"
        datos["moneda"] = "USD ($)"
        
        m_cons = re.search(r'Consecutivo:[\s\|]*(\d+)', texto)
        if m_cons:
            datos["num_factura"] = m_cons.group(1)
            
        m_cli = re.search(r'Nombre:[\s\|]*(.+)', texto)
        if m_cli:
            cli_raw = m_cli.group(1).split("Cédula:")[0].split("Teléfono:")[0].strip()
            datos["cliente"] = re.sub(r'^[\|:\s]+|[\|:\s]+$', '', cli_raw)
            
        m_fec = re.search(r'Fecha:[\s\|]*(\d{2}/\d{2}/\d{4})', texto)
        if m_fec:
            datos["fecha"] = m_fec.group(1)
            
        m_tot = re.search(r'Total:[\s\|]*([\d\.,]+)', texto)
        if m_tot:
            val_str = m_tot.group(1).replace('.', '').replace(',', '.')
            try:
                datos["monto_total"] = float(val_str)
            except ValueError:
                pass
                
        m_iva = re.search(r'I\.V\.A[\s\|]*([\d\.,]+)', texto)
        if m_iva:
            val_iva = m_iva.group(1).replace('.', '').replace(',', '.')
            try:
                datos["monto_iva"] = float(val_iva)
            except ValueError:
                pass
                
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    if not datos["num_factura"] and filename:
        datos["num_factura"] = filename.replace('.pdf', '')
        
    return datos
