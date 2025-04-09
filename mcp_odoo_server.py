# mcp_odoo_server.py

import os
import xmlrpc.client
import logging
from dotenv import load_dotenv
# Import principal de MCP (verificado que el paquete se llama 'mcp')
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List

# --- 1. Configuración del Logging ---
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# Asegura que el log se cree en el directorio actual
log_file_path = os.path.join(os.path.dirname(__file__), 'mcp_odoo_debug.log')
log_handler = logging.FileHandler(log_file_path, encoding='utf-8')
log_handler.setFormatter(log_formatter)

logger = logging.getLogger('mcp_odoo_server')
logger.setLevel(logging.DEBUG) # Captura todo desde DEBUG hacia arriba
# Limpia handlers previos si se re-ejecuta en algunos entornos interactivos
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(log_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO) # Muestra INFO y superior en consola
logger.addHandler(console_handler)

logger.info("Iniciando el servidor MCP para Odoo...")

# --- 2. Carga de Variables de Entorno ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
if load_dotenv(dotenv_path=env_path):
    logger.info(f"Archivo .env cargado desde: {env_path}")
else:
    logger.warning(f"Archivo .env no encontrado en {env_path}. Usando variables de entorno del sistema si existen.")

ODOO_URL = os.getenv('ODOO_URL')
ODOO_DB = os.getenv('ODOO_DB')
ODOO_USER = os.getenv('ODOO_USER')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD') # Clave API

required_vars = {'ODOO_URL': ODOO_URL, 'ODOO_DB': ODOO_DB, 'ODOO_USER': ODOO_USER, 'ODOO_PASSWORD': ODOO_PASSWORD}
missing_vars = [k for k, v in required_vars.items() if not v] # Verifica que no estén vacíos

if missing_vars:
    error_msg = f"Error Crítico: Faltan variables de entorno o están vacías: {', '.join(missing_vars)}. Revisa tu archivo .env o el entorno."
    logger.critical(error_msg)
    exit(1) # Salir si faltan variables críticas
else:
    logger.info("Variables de entorno de Odoo cargadas y validadas.")
    logger.debug(f"Configuración Odoo -> URL: {ODOO_URL}, DB: {ODOO_DB}, User: {ODOO_USER}")

# --- 3. Instanciación de FastMCP ---
try:
    app = FastMCP(name="quindicolor-odoo-agent")
    logger.info("Instancia de FastMCP<'quindicolor-odoo-agent'> creada.")
except Exception as e:
    logger.critical(f"Error inesperado al instanciar FastMCP: {e}", exc_info=True)
    exit(1)

# --- 4. Función de Conexión a Odoo (Versión simple: siempre reconecta) ---
def get_odoo_connection_details() -> Optional[Dict[str, Any]]:
    """
    Establece una conexión con Odoo usando XML-RPC y autentica al usuario.
    Utiliza las credenciales cargadas desde el entorno. Reconecta en cada llamada.

    Returns:
        Dict con detalles ('url', 'db', 'uid', 'password', 'models') o None si falla.
    """
    if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD]):
        logger.error("get_odoo_connection_details: Faltan variables de entorno Odoo.")
        return None

    common_url = f"{ODOO_URL.rstrip('/')}/xmlrpc/2/common"
    object_url = f"{ODOO_URL.rstrip('/')}/xmlrpc/2/object"

    try:
        logger.debug(f"Intentando conectar a common: {common_url}")
        common = xmlrpc.client.ServerProxy(common_url)
        common.version()
        logger.debug("Conexión a 'common' exitosa.")

        logger.debug(f"Autenticando usuario '{ODOO_USER}' en DB '{ODOO_DB}'...")
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})

        if not uid:
            logger.error(f"Fallo la autenticación Odoo para usuario '{ODOO_USER}' en DB '{ODOO_DB}'. Verifica credenciales.")
            return None
        logger.debug(f"Autenticación Odoo exitosa. UID: {uid}")

        logger.debug(f"Creando proxy para object: {object_url}")
        models = xmlrpc.client.ServerProxy(object_url)

        logger.info(f"Conexión Odoo preparada (UID: {uid}).")
        return {
            'url': ODOO_URL,
            'db': ODOO_DB,
            'uid': uid,
            'password': ODOO_PASSWORD,
            'models': models
        }

    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo: Fault {e.faultCode} - {e.faultString}", exc_info=True)
        return None
    except ConnectionRefusedError:
        logger.error(f"Error de conexión Odoo: No se pudo conectar a {ODOO_URL}. ¿Servidor Odoo activo y accesible?", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error inesperado durante conexión/autenticación Odoo: {type(e).__name__} - {e}", exc_info=True)
        return None

# --- 5. Herramientas MCP ---
@app.tool()
def buscar_cliente(nombre_cliente: str) -> str:
    """
    Busca clientes en Odoo cuyos nombres coincidan (parcialmente, sin importar mayúsculas/minúsculas)
    con el nombre proporcionado. Devuelve ID, Nombre, Email, Teléfono (máx 5).
    """
    logger.info(f"Ejecutando herramienta 'buscar_cliente' con nombre: '{nombre_cliente}'")
    if not nombre_cliente: return "Por favor, proporciona un nombre de cliente para buscar."
    conn = get_odoo_connection_details()
    if not conn: return "Error: No se pudo conectar con Odoo para buscar el cliente."
    try:
        domain = [['name', 'ilike', nombre_cliente]]
        fields = ['id', 'name', 'email', 'phone']
        limit = 5
        logger.debug(f"Odoo Call: model='res.partner', method='search_read', domain={domain}, fields={fields}, limit={limit}")
        clientes = conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'res.partner','search_read',[domain],{'fields': fields, 'limit': limit})
        logger.info(f"Odoo devolvió {len(clientes)} cliente(s) para '{nombre_cliente}'.")
        if not clientes: return f"No se encontraron clientes que coincidan con '{nombre_cliente}'."
        respuesta = f"Clientes encontrados para '{nombre_cliente}':\n"
        for c in clientes:
            respuesta += f"  - ID: {c.get('id', 'N/A')}, Nombre: {c.get('name', 'N/A')}, Email: {c.get('email', 'N/A')}, Teléfono: {c.get('phone', 'N/A')}\n"
        return respuesta.strip()
    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo en buscar_cliente: {e.faultCode} - {e.faultString}", exc_info=True)
        return f"Error de Odoo al buscar cliente: {e.faultString}"
    except Exception as e:
        logger.error(f"Error inesperado en buscar_cliente: {type(e).__name__} - {e}", exc_info=True)
        return f"Error inesperado del servidor al buscar cliente: {type(e).__name__}"

@app.tool()
def buscar_producto(nombre_producto: str) -> str:
    """
    Busca productos en Odoo cuyos nombres coincidan (parcialmente, sin importar mayúsculas/minúsculas)
    con el nombre proporcionado. Devuelve ID, Nombre, Código, Precio, Cant. Disponible (máx 5).
    """
    logger.info(f"Ejecutando herramienta 'buscar_producto' con nombre: '{nombre_producto}'")
    if not nombre_producto: return "Por favor, proporciona un nombre de producto para buscar."
    conn = get_odoo_connection_details()
    if not conn: return "Error: No se pudo conectar con Odoo para buscar el producto."
    try:
        domain = [['name', 'ilike', nombre_producto]]
        fields = ['id', 'name', 'default_code', 'list_price', 'qty_available']
        limit = 5
        logger.debug(f"Odoo Call: model='product.product', method='search_read', domain={domain}, fields={fields}, limit={limit}")
        productos = conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'product.product','search_read',[domain],{'fields': fields, 'limit': limit})
        logger.info(f"Odoo devolvió {len(productos)} producto(s) para '{nombre_producto}'.")
        if not productos: return f"No se encontraron productos que coincidan con '{nombre_producto}'."
        respuesta = f"Productos encontrados para '{nombre_producto}':\n"
        for p in productos:
            respuesta += f"  - ID: {p.get('id', 'N/A')}, Nombre: {p.get('name', 'N/A')}, Código: {p.get('default_code', 'N/A')}, Precio: {p.get('list_price', 'N/A')}, Disp: {p.get('qty_available', 'N/A')}\n"
        return respuesta.strip()
    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo en buscar_producto: {e.faultCode} - {e.faultString}", exc_info=True)
        return f"Error de Odoo al buscar producto: {e.faultString}"
    except Exception as e:
        logger.error(f"Error inesperado en buscar_producto: {type(e).__name__} - {e}", exc_info=True)
        return f"Error inesperado del servidor al buscar producto: {type(e).__name__}"

@app.tool()
def crear_cotizacion(cliente_id: int, lineas: List[Dict[str, Any]]) -> str:
    """
    Crea una nueva cotización (Orden de Venta) en Odoo para un cliente específico con las líneas de producto dadas.
    Args: cliente_id (ID del cliente), lineas (Lista de dicts {'product_id': ID_PROD, 'product_uom_qty': CANTIDAD}).
    Returns: ID de la cotización creada o mensaje de error.
    Ejemplo lineas: [{'product_id': 40, 'product_uom_qty': 2}, {'product_id': 35, 'product_uom_qty': 1}]
    """
    logger.info(f"Ejecutando herramienta 'crear_cotizacion' para cliente ID: {cliente_id}")
    logger.debug(f"Líneas recibidas: {lineas}")
    # (Validaciones de entrada omitidas por brevedad, pero presentes en la versión anterior)
    if not isinstance(cliente_id, int) or cliente_id <= 0: return "Error: Se requiere un ID de cliente válido."
    if not isinstance(lineas, list) or not lineas: return "Error: Se requiere al menos una línea de producto."
    # Aquí irían las validaciones detalladas de cada línea como antes...

    conn = get_odoo_connection_details()
    if not conn: return "Error: No se pudo conectar con Odoo para crear la cotización."
    try:
        order_lines_commands = []
        for linea in lineas:
             # Validar formato de línea aquí también es buena idea
             if not isinstance(linea, dict) or 'product_id' not in linea or 'product_uom_qty' not in linea:
                 return f"Error: Formato de línea inválido: {linea}. Se requiere 'product_id' y 'product_uom_qty'."
             try:
                qty = float(linea['product_uom_qty'])
                if qty <= 0: return f"Error: Cantidad debe ser positiva en línea: {linea}"
             except (ValueError, TypeError):
                 return f"Error: Cantidad no numérica en línea: {linea}"

             linea_vals = {'product_id': linea['product_id'],'product_uom_qty': linea['product_uom_qty'],}
             order_lines_commands.append((0, 0, linea_vals))

        valores_cotizacion = {'partner_id': cliente_id,'order_line': order_lines_commands,}
        logger.debug(f"Odoo Call: model='sale.order', method='create', values={valores_cotizacion}")
        cotizacion_id = conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'sale.order','create',[valores_cotizacion])
        logger.info(f"Cotización creada exitosamente en Odoo con ID: {cotizacion_id}")
        return f"Cotización creada exitosamente con ID: {cotizacion_id}"
    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo en crear_cotizacion: {e.faultCode} - {e.faultString}", exc_info=True)
        error_msg = f"Error de Odoo al crear cotización: {e.faultString}"
        if "Missing required fields" in e.faultString: error_msg += ". Posiblemente falten campos obligatorios."
        elif "Not possible to determine the pricelist" in e.faultString: error_msg += ". Cliente sin tarifa?"
        return error_msg
    except Exception as e:
        logger.error(f"Error inesperado en crear_cotizacion: {type(e).__name__} - {e}", exc_info=True)
        return f"Error inesperado del servidor al crear cotización: {type(e).__name__}"

@app.tool()
def confirmar_cotizacion(cotizacion_id: int) -> str:
    """
    Confirma una cotización (Orden de Venta) en Odoo usando su ID.
    Verifica el estado antes y después. La cotización debe estar en 'draft' o 'sent'.
    """
    logger.info(f"Ejecutando herramienta 'confirmar_cotizacion' para ID: {cotizacion_id}")
    if not isinstance(cotizacion_id, int) or cotizacion_id <= 0: return "Error: ID de cotización inválido."
    conn = get_odoo_connection_details()
    if not conn: return "Error: No se pudo conectar con Odoo."
    try:
        # Verificar estado previo
        read_result = conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'sale.order', 'read', [[cotizacion_id]], {'fields': ['state']})
        if not read_result: return f"Error: No se encontró cotización con ID {cotizacion_id}."
        estado_previo = read_result[0].get('state')
        logger.info(f"Estado cotización {cotizacion_id} ANTES: '{estado_previo}'")
        if estado_previo not in ['draft', 'sent']: return f"Error: Cotización {cotizacion_id} en estado '{estado_previo}', no se puede confirmar."

        # Confirmar
        logger.debug(f"Odoo Call: model='sale.order', method='action_confirm', args=[[{cotizacion_id}]]")
        conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'sale.order','action_confirm',[[cotizacion_id]])
        logger.info(f"'action_confirm' llamado para cotización {cotizacion_id}.")

        # Verificar estado posterior
        read_result_after = conn['models'].execute_kw(conn['db'], conn['uid'], conn['password'],'sale.order', 'read', [[cotizacion_id]], {'fields': ['state']})
        if not read_result_after: return f"Error inesperado: Cotización {cotizacion_id} no encontrada después de confirmar."
        estado_posterior = read_result_after[0].get('state')
        logger.info(f"Estado cotización {cotizacion_id} DESPUÉS: '{estado_posterior}'")

        if estado_posterior == 'sale': return f"Cotización {cotizacion_id} confirmada. Nuevo estado: Pedido de Venta (sale)."
        elif estado_posterior == estado_previo: return f"Se intentó confirmar cotización {cotizacion_id}, pero sigue en '{estado_posterior}'. Revisa Odoo."
        else: return f"Cotización {cotizacion_id} procesada. Estado actual: '{estado_posterior}'."
    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo en confirmar_cotizacion: {e.faultCode} - {e.faultString}", exc_info=True)
        error_msg = f"Error de Odoo al confirmar cotización {cotizacion_id}: {e.faultString}"
        if "You can not confirm a sales order which is empty." in e.faultString: error_msg += " La cotización no tiene líneas."
        return error_msg
    except Exception as e:
        logger.error(f"Error inesperado en confirmar_cotizacion: {type(e).__name__} - {e}", exc_info=True)
        return f"Error inesperado del servidor al confirmar cotización: {type(e).__name__}"
@app.tool()
def listar_productos() -> str:
    """
    Lista los primeros 20 productos vendibles disponibles en Odoo.

    Args:
        None

    Returns:
        Una cadena de texto formateada con la lista de productos (ID, Nombre, Código, Precio)
        o un mensaje de error.
    """
    logger.info(f"Tool: listar_productos ejecutado.")
    conn = get_odoo_connection_details()
    if not conn: return "Error: No se pudo conectar con Odoo."
    try:
        # Dominio para buscar solo productos que se pueden vender
        domain = [['sale_ok', '=', True]]
        # Campos útiles (quitamos qty_available para que sea más rápido)
        fields = ['id', 'name', 'default_code', 'list_price']
        limit = 20 # Límite para no sobrecargar

        logger.debug(f"Odoo Call: product.product.search_read, domain={domain}, fields={fields}, limit={limit}")
        productos = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'product.product','search_read',
            [domain],
            {'fields': fields, 'limit': limit}
        )
        logger.info(f"Odoo devolvió {len(productos)} producto(s) (límite {limit}).")

        if not productos: return "No se encontraron productos vendibles."

        respuesta = f"Mostrando los primeros {len(productos)} productos vendibles:\n"
        for p in productos:
            respuesta += f"  - ID:{p.get('id')} Nom:{p.get('name')} Cod:{p.get('default_code','-')} P:{p.get('list_price',0)}\n"
        return respuesta.strip()

    except xmlrpc.client.Fault as e:
        logger.error(f"Error Odoo en listar_productos: {e.faultString}")
        return f"Error Odoo al listar productos: {e.faultString}"
    except Exception as e:
        logger.error(f"Error inesperado en listar_productos: {e}", exc_info=True)
        return f"Error servidor al listar productos: {type(e).__name__}"

# --- HERRAMIENTA ELIMINADA ---
# La función crear_factura_desde_pedido(pedido_id: int) -> str fue eliminada
# debido a la complejidad y restricciones de tiempo, y al error de método privado.

# --- 6. Bloque Principal ---
if __name__ == "__main__":
    logger.info("Ejecutando bloque principal (__name__ == '__main__').")
    logger.info("Realizando verificación inicial de conexión a Odoo...")
    initial_conn = get_odoo_connection_details()
    if initial_conn:
        logger.info("Verificación inicial de conexión Odoo: ÉXITO.")
        try:
             access_check = initial_conn['models'].execute_kw(
                 initial_conn['db'], initial_conn['uid'], initial_conn['password'],
                 'res.users', 'check_access_rights', ['read'], {'raise_exception': False}
             )
             logger.info(f"Verificación de acceso ('res.users', 'read'): {access_check}")
        except Exception as e:
             logger.warning(f"Fallo en llamada de verificación de acceso post-conexión: {e}", exc_info=True)
    else:
        logger.error("Verificación inicial de conexión Odoo: FALLÓ. Revisa logs y configuración.")
        # exit(1) # Descomentar si es crítico que la conexión inicial funcione

    logger.info("Iniciando el servidor MCP FastMCP en modo stdio...")
    try:
        app.run(transport='stdio')
        logger.info("Servidor MCP detenido.")
    except Exception as e:
        logger.critical(f"Error fatal al ejecutar el servidor MCP app.run(): {e}", exc_info=True)
        exit(1)