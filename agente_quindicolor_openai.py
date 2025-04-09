# agente_quindicolor_openai.py (v4 - Refactorizado para Gradio)

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
    # Asumiendo que la definición de StdioServerParameters es interna o no necesaria aquí
except ImportError as e:
    print(f"Error importando 'openai-agents'. ¿Instalado? Detalle: {e}")
    exit(1)

# --- Configuración Logger (igual que antes) ---
agent_logger = logging.getLogger('openai_agent_logic') # Cambiado nombre para diferenciar
agent_logger.setLevel(logging.INFO)
agent_console_handler = logging.StreamHandler()
agent_console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if agent_logger.hasHandlers():
    agent_logger.handlers.clear()
agent_logger.addHandler(agent_console_handler)

# --- Carga de .env (igual que antes) ---
env_path = os.path.join(os.path.dirname(__file__), '.env')
if load_dotenv(dotenv_path=env_path):
    agent_logger.info(f".env cargado para la lógica del agente: {env_path}")
else:
    agent_logger.warning(".env no encontrado. OPENAI_API_KEY debe estar definida.")
# (Validación de OPENAI_API_KEY omitida por brevedad, pero debería estar)


# --- Configuración Conexión MCP Odoo (igual que antes) ---
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
agent_logger.info("Conector MCPServerStdio configurado.")


# --- Definición del Agente OpenAI (igual que antes) ---
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
        "6. Construye la lista de líneas en el formato JSON requerido por la herramienta 'crear_cotizacion'.\n"
        "7. Usa 'crear_cotizacion' con el ID del cliente y la lista de líneas.\n"
        "Cuando te pidan confirmar una cotización, usa 'confirmar_cotizacion'."
        "Informa al usuario de las acciones que realizas y de los resultados."
        "Si un producto no tiene stock, informa al usuario y pregunta cómo proceder."
    ),
    model="gpt-4o",
    mcp_servers=[odoo_mcp_server]
)
agent_logger.info("Agente OpenAI definido.")

# --- NUEVA FUNCIÓN ASÍNCRONA PARA PROCESAR UN TURNO ---
async def process_agent_turn(user_input: str, history: list) -> Tuple[list, str]:
    """
    Procesa un turno de conversación: recibe input del usuario y el historial,
    ejecuta el agente, actualiza el historial y devuelve la respuesta en texto.

    Args:
        user_input: El último mensaje del usuario.
        history: El historial de la conversación en formato [{'role': 'user'/'assistant', 'content': ...}]

    Returns:
        Una tupla: (nuevo_historial_completo, respuesta_texto_asistente)
    """
    agent_logger.info(f"Procesando turno. Historial actual: {len(history)} mensajes. Input: '{user_input}'")
    current_history = history + [{"role": "user", "content": user_input}]

    response_text = "(El agente no generó respuesta en texto)" # Valor por defecto
    assistant_response_for_history = None # Para guardar el mensaje completo del asistente

    try:
        # El contexto async with gestiona la conexión/desconexión del MCP server para esta llamada
        # NOTA: Esto puede ser ineficiente si el servidor MCP tarda en arrancar.
        # Una optimización sería mantener el servidor corriendo globalmente.
        async with odoo_mcp_server:
            agent_logger.info("Contexto MCPServerStdio activo para la llamada a Runner.run.")
            result = await Runner.run(
                starting_agent=agente_quindicolor,
                input=current_history
            )
            agent_logger.info(f"Runner.run completado. Items nuevos: {len(result.new_items)}")

            # Procesar la respuesta del agente (similar a antes)
            if result.final_output:
                response_text = str(result.final_output)
                assistant_response_for_history = {"role": "assistant", "content": response_text}
            else:
                last_assistant_message_parts = []
                text_parts = []
                for item in result.new_items:
                    if item.type == "message_output_item":
                        content = getattr(item.raw, 'content', None) # Acceso seguro al atributo
                        if isinstance(content, list):
                            last_assistant_message_parts.extend(content)
                            text_parts.extend([part.text for part in content if hasattr(part, 'text')])
                        elif content and hasattr(content, 'text'):
                            last_assistant_message_parts.append(content)
                            text_parts.append(content.text)
                    elif item.type == "tool_call_item":
                         tool_call_content = getattr(item.raw, 'tool_calls', [getattr(item.raw, 'tool_call', None)]) # Compatibilidad
                         if tool_call_content[0]: # Si hay llamada
                              last_assistant_message_parts.append(tool_call_content[0])

                if last_assistant_message_parts:
                    assistant_response_for_history = {"role": "assistant", "content": last_assistant_message_parts}
                    response_text = "\n".join(filter(None, text_parts)).strip()
                    if not response_text and any(item.type in ["tool_call_item", "tool_call_output_item"] for item in result.new_items):
                        response_text = "(Acción interna realizada...)"

        # Actualizar historial y devolver
        if assistant_response_for_history:
            updated_history = current_history + [assistant_response_for_history]
        else:
            updated_history = current_history # No añadir nada si el asistente no respondió
            agent_logger.warning("No se generó contenido del asistente para añadir al historial.")

        agent_logger.info(f"Turno procesado. Respuesta: '{response_text[:50]}...'. Historial nuevo: {len(updated_history)} mensajes.")
        return updated_history, response_text

    except Exception as e:
        agent_logger.error(f"Error en process_agent_turn: {type(e).__name__} - {e}", exc_info=True)
        # Devolver el error como respuesta y mantener el historial anterior
        error_message = f"Error procesando la solicitud: {type(e).__name__}"
        # Podríamos intentar añadir un mensaje de error al historial si quisiéramos
        # updated_history = current_history + [{"role": "assistant", "content": error_message}]
        # return updated_history, error_message
        return current_history, error_message # Mantenemos historial simple en caso de error

# --- Bloque Principal (ya no ejecuta el chat) ---
if __name__ == "__main__":
    agent_logger.warning("Este script está diseñado para ser importado por la app Gradio (app_gradio.py).")
    agent_logger.warning("No ejecutará un chat interactivo si se corre directamente.")
    # Podríamos añadir aquí una prueba simple de la función si quisiéramos:
    # async def test_run():
    #     hist, resp = await process_agent_turn("Busca cliente Marc Demo", [])
    #     print("Respuesta Test:", resp)
    # asyncio.run(test_run())
    pass