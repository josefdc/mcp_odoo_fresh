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

logger.info("Iniciando el servidor MCP para Odoo (entorno fresco)...")

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
    # No loguear la clave API/contraseña
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
    # Las variables ya se validaron al inicio, pero una comprobación rápida no hace daño
    if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD]):
        logger.error("get_odoo_connection_details: Faltan variables de entorno Odoo.")
        return None

    common_url = f"{ODOO_URL.rstrip('/')}/xmlrpc/2/common"
    object_url = f"{ODOO_URL.rstrip('/')}/xmlrpc/2/object"

    try:
        logger.debug(f"Intentando conectar a common: {common_url}")
        common = xmlrpc.client.ServerProxy(common_url)
        # Llamada simple para verificar conectividad con common
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
            'password': ODOO_PASSWORD, # Necesario para execute_kw
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

# --- 5. Herramientas MCP (A implementar) ---
@app.tool()
def buscar_cliente(nombre_cliente: str) -> str:
    """
    Busca clientes en Odoo cuyos nombres coincidan (parcialmente, sin importar mayúsculas/minúsculas)
    con el nombre proporcionado.

    Args:
        nombre_cliente: El nombre (o parte del nombre) del cliente a buscar.

    Returns:
        Una cadena de texto formateada con los resultados de la búsqueda (ID, Nombre, Email, Teléfono)
        o un mensaje indicando si no se encontraron resultados o si ocurrió un error.
        Se devuelven un máximo de 5 resultados.
    """
    logger.info(f"Ejecutando herramienta 'buscar_cliente' con nombre: '{nombre_cliente}'")

    if not nombre_cliente:
        logger.warning("buscar_cliente: Se recibió un nombre de cliente vacío.")
        return "Por favor, proporciona un nombre de cliente para buscar."

    # 1. Obtener conexión a Odoo
    conn = get_odoo_connection_details()
    if not conn:
        logger.error("buscar_cliente: No se pudo obtener la conexión a Odoo.")
        return "Error: No se pudo conectar con Odoo para buscar el cliente."

    try:
        # 2. Preparar parámetros para search_read
        domain = [['name', 'ilike', nombre_cliente]] # 'ilike' es case-insensitive
        fields = ['id', 'name', 'email', 'phone']
        limit = 5 # Limitar la cantidad de resultados

        logger.debug(f"Llamando a Odoo: model='res.partner', method='search_read', domain={domain}, fields={fields}, limit={limit}")

        # 3. Llamar a Odoo usando execute_kw
        clientes_encontrados = conn['models'].execute_kw(
            conn['db'], conn['uid'], conn['password'],
            'res.partner',  # Modelo a buscar
            'search_read',  # Método a ejecutar
            [domain],       # Argumentos posicionales (lista que contiene el dominio)
            {'fields': fields, 'limit': limit} # Argumentos de palabra clave (kwargs)
        )

        logger.info(f"Odoo devolvió {len(clientes_encontrados)} cliente(s) para la búsqueda '{nombre_cliente}'.")

        # 4. Procesar y formatear la respuesta
        if not clientes_encontrados:
            return f"No se encontraron clientes que coincidan con '{nombre_cliente}'."
        else:
            respuesta_formateada = f"Clientes encontrados para '{nombre_cliente}':\n"
            for cliente in clientes_encontrados:
                respuesta_formateada += (
                    f"  - ID: {cliente.get('id', 'N/A')}, "
                    f"Nombre: {cliente.get('name', 'N/A')}, "
                    f"Email: {cliente.get('email', 'N/A')}, "
                    f"Teléfono: {cliente.get('phone', 'N/A')}\n"
                )
            return respuesta_formateada.strip() # Elimina el último salto de línea

    except xmlrpc.client.Fault as e:
        logger.error(f"Error XML-RPC Odoo en buscar_cliente: {e.faultCode} - {e.faultString}", exc_info=True)
        return f"Error de Odoo al buscar cliente: {e.faultString}"
    except Exception as e:
        logger.error(f"Error inesperado en buscar_cliente: {type(e).__name__} - {e}", exc_info=True)
        return f"Error inesperado del servidor al buscar cliente: {type(e).__name__}"


# --- 6. Bloque Principal ---
if __name__ == "__main__":
    logger.info("Ejecutando bloque principal (__name__ == '__main__').")

    # Verificación inicial de conexión (opcional pero útil para depurar al inicio)
    logger.info("Realizando verificación inicial de conexión a Odoo...")
    initial_conn = get_odoo_connection_details()
    if initial_conn:
        logger.info("Verificación inicial de conexión Odoo: ÉXITO.")
        # Podemos hacer una llamada simple para confirmar que 'models' funciona
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
        # Considera salir si es crítico: exit(1)

    logger.info("Iniciando el servidor MCP FastMCP en modo stdio...")
    try:
        # transport='stdio' es necesario para mcp dev / Claude Desktop
        app.run(transport='stdio')
        # Esta línea solo se alcanza si el servidor se detiene limpiamente
        logger.info("Servidor MCP detenido.")
    except Exception as e:
        logger.critical(f"Error fatal al ejecutar el servidor MCP app.run(): {e}", exc_info=True)
        exit(1)