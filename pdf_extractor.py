import re
from pypdf import PdfReader

def parse_latam_number(val_str):
    if not val_str:
        return 0.0
    val_str = str(val_str).strip()
    if ',' in val_str and '.' in val_str:
        if val_str.rfind(',') > val_str.rfind('.'):
            val_str = val_str.replace('.', '').replace(',', '.')
        else:
            val_str = val_str.replace(',', '')
    elif ',' in val_str and '.' not in val_str:
        val_str = val_str.replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def get_guatemala_total_and_iva(texto):
    m_tot_line = re.search(r'TOTALES:[\s\S]*?(?:IVA|$)', texto)
    m_total = None
    m_iva = None
    if m_tot_line:
        block = m_tot_line.group(0)
        numbers = re.findall(r'[\d,]+\.\d{2}', block)
        if len(numbers) >= 3:
            m_total = parse_latam_number(numbers[-1])
        elif len(numbers) >= 1:
            m_total = parse_latam_number(numbers[0])
            
    m_iva_match = re.search(r'TOTALES:[\s\S]*?IVA[\s\|]*([\d,]+\.\d{2,7})', texto)
    if m_iva_match:
        m_iva = parse_latam_number(m_iva_match.group(1))
        
    return m_total, m_iva

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
    
    # ----------------------------------------------------
    # 1. HONDURAS (Detección por CAI, RTN o Lempiras)
    # ----------------------------------------------------
    if "CAI" in texto or "05081975001517" in texto or "LEMPIRAS" in texto.upper() or "RTN" in texto or "HONDURAS" in texto.upper():
        datos["pais"] = "Honduras"
        datos["moneda"] = "HNL (L)"
        
        # N° Factura (Priorizar coincidencia tras la palabra FACTURA para evitar el Rango Autorizado)
        m_fac_after = re.search(r'FACTURA[\s\S]{1,100}?(\d{3}-\d{3}-\d{2}-\d{5})[\s\S]{0,10}?(\d{3})', texto, re.IGNORECASE)
        if m_fac_after:
            datos["num_factura"] = f"{m_fac_after.group(1)}{m_fac_after.group(2)}"
        else:
            m_fac_after2 = re.search(r'FACTURA[\s\S]{1,100}?(\d{3}-\d{3}-\d{2}-\d{8})', texto, re.IGNORECASE)
            if m_fac_after2:
                datos["num_factura"] = m_fac_after2.group(1)
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
        m_tot = re.search(r'Total\s+a\s+Pagar[\s\S]{1,150}?([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if m_tot:
            datos["monto_total"] = parse_latam_number(m_tot.group(1))
            
        # 15% ISV
        m_isv = re.search(r'15%\s*I\.?S\.?V\.?[\s\S]{1,150}?([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if m_isv:
            datos["monto_iva"] = parse_latam_number(m_isv.group(1))
            
        # Importe Gravado / Neto
        m_neto = re.search(r'Importe\s+Gravado[\s\S]{1,150}?([\d,]+\.\d{2})', texto, re.IGNORECASE)
        if m_neto:
            datos["monto_neto"] = parse_latam_number(m_neto.group(1))
        else:
            datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # ----------------------------------------------------
    # 2. GUATEMALA (Detección por FEL / SAT / NIT / DTE)
    # ----------------------------------------------------
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
            
        # Total e IVA
        tot_gt, iva_gt = get_guatemala_total_and_iva(texto)
        if tot_gt is not None:
            datos["monto_total"] = tot_gt
        if iva_gt is not None:
            datos["monto_iva"] = iva_gt
            
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    # ----------------------------------------------------
    # 3. COSTA RICA (Detección por Consecutivo / Clave / Cédula 3-101)
    # ----------------------------------------------------
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
            datos["monto_total"] = parse_latam_number(m_tot.group(1))
                
        m_iva = re.search(r'I\.V\.A:?[\s\|]*([\d\.,]+)', texto)
        if m_iva:
            datos["monto_iva"] = parse_latam_number(m_iva.group(1))
                
        datos["monto_neto"] = round(datos["monto_total"] - datos["monto_iva"], 2)

    if not datos["num_factura"] and filename:
        datos["num_factura"] = filename.replace('.pdf', '')
        
    return datos
