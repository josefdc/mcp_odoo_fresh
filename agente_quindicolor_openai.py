# agente_quindicolor_openai.py (v5 - Estable, Refactorizado para Gradio, SIN Streaming)

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
    agent_logger.critical("Error: OPENAI_API_KEY no encontrada.")

# --- Configuración Conexión MCP Odoo ---
agent_logger.info("Configurando conexión al servidor MCP Odoo...")
mcp_server_script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "mcp_odoo_server.py"))
if not os.path.exists(mcp_server_script_path):
    agent_logger.critical(f"Script MCP no encontrado: {mcp_server_script_path}")
    exit(1)
odoo_server_params_dict = {
    "command": sys.executable,
    "args": [mcp_server_script_path],
    "cwd": os.path.dirname(mcp_server_script_path)
}
odoo_mcp_server = MCPServerStdio(params=odoo_server_params_dict)
agent_logger.info(f"Conector MCPServerStdio configurado para: {sys.executable} {mcp_server_script_path}")

# --- Definición del Agente OpenAI ---
agent_logger.info("Definiendo el Agente OpenAI 'AsistenteQuindicolor'...")
agente_quindicolor = Agent(
    name="AsistenteQuindicolor",
    instructions=(
        "Eres un asistente experto en ventas para QuindíColor que interactúa con Odoo.\n"
        "Puedes usar las siguientes herramientas:\n"
        "- 'buscar_cliente': Encuentra clientes por nombre.\n"
        "- 'buscar_producto': Busca productos específicos por nombre.\n"
        "- 'listar_productos': Muestra una lista inicial de productos vendibles (hasta 20).\n" # <-- Nueva herramienta añadida
        "- 'crear_cotizacion': Crea una nueva cotización con cliente y líneas de producto (IDs y cantidades).\n"
        "- 'confirmar_cotizacion': Confirma una cotización existente por su ID.\n"
        "\n"
        "Flujo para crear cotización:\n"
        "1. Usa 'buscar_cliente' para obtener el ID.\n"
        "2. Pregunta al usuario qué productos/cantidades añadir.\n"
        "3. Usa 'buscar_producto' para obtener los IDs de esos productos.\n"
        "4. Construye la lista de líneas JSON: [{'product_id': ID, 'product_uom_qty': QTY}, ...].\n"
        "5. Llama a 'crear_cotizacion'.\n"
        "\n"
        "Si el usuario pide ver productos en general, usa 'listar_productos'.\n"
        "Si un producto buscado no tiene stock, informa y pregunta antes de continuar.\n"
        "Sé conciso e informa de tus acciones y resultados."
    ),
    model="gpt-4o-2024-11-20",
    mcp_servers=[odoo_mcp_server]
)
agent_logger.info("Agente OpenAI definido.")

# --- FUNCIÓN ASÍNCRONA PARA PROCESAR UN TURNO (SIN STREAMING) ---
async def process_agent_turn(user_input: str, history: list) -> Tuple[list, str, Any | None]:
    """
    Procesa un turno: recibe input y historial previo, ejecuta agente, devuelve
    historial actualizado, texto de respuesta y contenido completo de la respuesta del asistente.
    """
    agent_logger.info(f"Procesando turno v2 (No Stream). Historial previo: {len(history)} msgs. Input: '{user_input}'")
    current_history_for_agent = history + [{"role": "user", "content": user_input}]

    response_text = "(El agente no generó respuesta en texto)"
    assistant_content_for_history = None

    try:
        # Usamos async with para asegurar que la conexión MCP esté activa durante el run
        async with odoo_mcp_server:
            agent_logger.info(f"Contexto MCP activo. Llamando a Runner.run con {len(current_history_for_agent)} mensajes.")
            result = await Runner.run(
                starting_agent=agente_quindicolor,
                input=current_history_for_agent
            )
            agent_logger.info(f"Runner.run completado. Items nuevos: {len(result.new_items)}")

            # Procesar respuesta
            if result.final_output:
                response_text = str(result.final_output)
                assistant_content_for_history = response_text # Guardar texto simple
            else:
                # Reconstruir texto y contenido completo si no hubo final_output
                last_assistant_message_parts = []
                text_parts = []
                raw_content_to_save = None
                for item in result.new_items:
                    if item.type == "message_output_item":
                        content = getattr(item.raw, 'content', None)
                        if content:
                             raw_content_to_save = content
                             if isinstance(content, list):
                                  text_parts.extend([part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"])
                             elif isinstance(content, dict) and content.get("type") == "text":
                                  text_parts.append(content.get("text", ""))
                
                response_text = "\n".join(filter(None, text_parts)).strip()
                assistant_content_for_history = raw_content_to_save # Guardar contenido completo
                if not response_text and any(item.type == "tool_call_item" for item in result.new_items):
                     response_text = "(Acción interna realizada...)"

        # Crear historial actualizado fuera del 'async with'
        updated_history = current_history_for_agent
        if assistant_content_for_history is not None:
            updated_history = updated_history + [{"role": "assistant", "content": assistant_content_for_history}]
        else:
            # Si no hubo respuesta del asistente, añadir placeholder o texto acumulado
            updated_history = updated_history + [{"role": "assistant", "content": response_text or "(Sin respuesta final)"}]
            agent_logger.warning("No se encontró contenido estructurado del asistente.")

        agent_logger.info(f"Turno v2 procesado. Respuesta: '{response_text[:50]}...'. Historial nuevo: {len(updated_history)} msgs.")
        return updated_history, response_text, assistant_content_for_history

    except Exception as e:
        agent_logger.error(f"Error en process_agent_turn v2: {type(e).__name__} - {e}", exc_info=True)
        error_message = f"Error procesando la solicitud: {type(e).__name__} ({e})"
        # Devolvemos historial ANTES del input del usuario que causó el error
        return history, error_message, None

# --- Bloque Principal ---
if __name__ == "__main__":
    agent_logger.warning("Este script ('agente_quindicolor_openai.py') contiene la lógica del agente.")
    agent_logger.warning("Ejecuta las apps Gradio para interactuar.")
    pass