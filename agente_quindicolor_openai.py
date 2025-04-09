# agente_quindicolor_openai.py (v5 - Refactorizado para Gradio)

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any, Tuple

# --- Imports del SDK ---
try:
    from agents import Agent, Runner
    from agents.mcp import MCPServerStdio
except ImportError as e:
    print(f"Error importando 'openai-agents'. ¿Instalado? Detalle: {e}")
    exit(1)

# --- Configuración Logger ---
agent_logger = logging.getLogger('openai_agent_logic')
agent_logger.setLevel(logging.INFO)
# Evitar duplicar handlers si se reimporta
if not agent_logger.handlers:
    agent_console_handler = logging.StreamHandler()
    agent_console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    agent_logger.addHandler(agent_console_handler)

# --- Carga de .env ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
if load_dotenv(dotenv_path=env_path):
    agent_logger.info(f".env cargado para la lógica del agente: {env_path}")
else:
    agent_logger.warning(".env no encontrado. OPENAI_API_KEY debe estar definida.")

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    agent_logger.critical("Error: OPENAI_API_KEY no encontrada. Define la variable en .env o en el entorno.")
    # No salimos aquí, pero la librería openai fallará después si no está configurada globalmente
    # exit(1)


# --- Configuración Conexión MCP Odoo ---
agent_logger.info("Configurando conexión al servidor MCP Odoo...")
mcp_server_script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_odoo_server.py"))
if not os.path.exists(mcp_server_script_path):
    agent_logger.critical(f"Script MCP no encontrado: {mcp_server_script_path}")
    exit(1)
odoo_server_params_dict = {
    "command": sys.executable, # Usa el python del venv actual
    "args": [mcp_server_script_path],
    "cwd": os.path.dirname(mcp_server_script_path) # Directorio de trabajo
}
# Crear la instancia del conector MCP Odoo (se usará en la función process_agent_turn)
odoo_mcp_server = MCPServerStdio(params=odoo_server_params_dict)
agent_logger.info(f"Conector MCPServerStdio configurado para: {sys.executable} {mcp_server_script_path}")


# --- Definición del Agente OpenAI ---
agent_logger.info("Definiendo el Agente OpenAI 'AsistenteQuindicolor'...")
agente_quindicolor = Agent(
    name="AsistenteQuindicolor",
    instructions=(
        "Eres un asistente experto en ventas para QuindíColor que interactúa con Odoo.\n"
        "Puedes usar herramientas para buscar clientes, buscar productos, crear cotizaciones y confirmar cotizaciones.\n"
        "Cuando te pidan crear una cotización:\n"
        "1. Usa 'buscar_cliente' para obtener el ID del cliente.\n"
        "2. Pregunta al usuario explícitamente: '¿Qué productos y cantidades quieres añadir a la cotización?'\n"
        "3. Espera la respuesta del usuario con los detalles de los productos.\n"
        "4. Extrae los nombres y cantidades de la respuesta del usuario.\n"
        "5. Usa 'buscar_producto' para obtener el ID de CADA producto mencionado.\n"
        "6. Construye la lista de líneas en el formato JSON requerido por la herramienta 'crear_cotizacion'. El formato es una lista de diccionarios, cada uno con 'product_id' (entero) y 'product_uom_qty' (número). Ejemplo: [{'product_id': 40, 'product_uom_qty': 2}, {'product_id': 38, 'product_uom_qty': 1}]\n"
        "7. Usa 'crear_cotizacion' con el ID del cliente y la lista de líneas construida.\n"
        "Cuando te pidan confirmar una cotización, usa 'confirmar_cotizacion' pasando el ID numérico.\n"
        "Informa al usuario de las acciones que realizas y de los resultados de forma concisa.\n"
        "Si un producto no tiene stock al buscarlo, informa al usuario y pregunta cómo proceder antes de intentar crear la cotización."
    ),
    model="gpt-4o", # O el modelo que prefieras/tengas acceso
    mcp_servers=[odoo_mcp_server] # Pasar la instancia del conector aquí
)
agent_logger.info("Agente OpenAI definido.")

# --- FUNCIÓN ASÍNCRONA PARA PROCESAR UN TURNO ---
async def process_agent_turn(user_input: str, history: list) -> Tuple[list, str, Any | None]:
    """
    Procesa un turno: recibe input y historial previo, ejecuta agente, devuelve
    historial actualizado, texto de respuesta y contenido completo de la respuesta del asistente.
    """
    agent_logger.info(f"Procesando turno v2. Historial previo: {len(history)} msgs. Input: '{user_input}'")
    current_history_for_agent = history + [{"role": "user", "content": user_input}]

    response_text = "(El agente no generó respuesta en texto)"
    assistant_content_for_history = None

    try:
        # Usar el mismo conector MCP definido globalmente
        # El contexto async with ahora se maneja externamente (en Gradio o un loop superior)
        # Aquí asumimos que odoo_mcp_server está activo o Runner.run lo activa internamente
        # Nota: La documentación de openai-agents sugiere que el Runner maneja la activación
        # del servidor MCP si se le pasa en la definición del Agente.

        agent_logger.info(f"Llamando a Runner.run con historial de {len(current_history_for_agent)} mensajes.")
        result = await Runner.run(
            starting_agent=agente_quindicolor,
            input=current_history_for_agent
        )
        agent_logger.info(f"Runner.run completado. Items nuevos: {len(result.new_items)}")

        # Procesar respuesta
        if result.final_output:
            response_text = str(result.final_output)
            assistant_content_for_history = response_text
        else:
            last_assistant_message_parts = []
            text_parts = []
            for item in result.new_items:
                if item.type == "message_output_item":
                    content = getattr(item.raw, 'content', None)
                    if content:
                         assistant_content_for_history = content # Guardar el más reciente
                         if isinstance(content, list):
                              text_parts.extend([part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"])
                         elif isinstance(content, dict) and content.get("type") == "text":
                              text_parts.append(content.get("text", ""))
                elif item.type == "tool_call_item":
                     # Para el historial, podríamos necesitar guardar la llamada
                     # Esto depende de si queremos que el LLM vea sus propias llamadas a herramientas
                     # Por ahora, el contenido para el historial será el último 'message_output_item'
                     pass # No añadir llamada a historial de texto

            response_text = "\n".join(filter(None, text_parts)).strip()
            if not response_text and any(item.type == "tool_call_item" for item in result.new_items):
                 response_text = "(Acción interna realizada...)"

        # Crear historial actualizado para devolver
        updated_history = current_history_for_agent
        if assistant_content_for_history:
            # Asegurarse de añadir la respuesta correcta al historial
            updated_history = updated_history + [{"role": "assistant", "content": assistant_content_for_history}]
        else:
            agent_logger.warning("No se generó contenido del asistente para añadir al historial.")

        agent_logger.info(f"Turno procesado v2. Respuesta: '{response_text[:50]}...'. Historial nuevo: {len(updated_history)} msgs.")
        return updated_history, response_text, assistant_content_for_history

    except Exception as e:
        agent_logger.error(f"Error en process_agent_turn v2: {type(e).__name__} - {e}", exc_info=True)
        error_message = f"Error procesando la solicitud: {type(e).__name__}"
        # Devolvemos historial ANTES del input del usuario que causó el error
        return history, error_message, None

# --- Bloque Principal (solo para info) ---
if __name__ == "__main__":
    agent_logger.warning("Este script ('agente_quindicolor_openai.py') contiene la lógica del agente.")
    agent_logger.warning("Ejecuta 'python app_gradio.py' para iniciar la interfaz de usuario.")
    pass