# app_gradio.py

import gradio as gr
import asyncio
import logging

# Importar la lógica refactorizada del agente y las instancias necesarias
try:
    from agente_quindicolor_openai import (
        agente_quindicolor,
        odoo_mcp_server, # Necesitamos pasar esto a la función
        process_agent_turn,
        agent_logger # Usar el mismo logger para consistencia
    )
except ImportError:
    print("Error: No se pudo importar desde agente_quindicolor_openai.py. Asegúrate de que exista y no tenga errores de sintaxis.")
    exit(1)

# --- Lógica de la Interfaz Gradio ---

# Función que Gradio llamará para cada interacción del chat
async def handle_chat(message: str, history_list_gradio: list, history_state_agent: list):
    """
    Maneja la entrada del usuario desde Gradio, llama al agente y actualiza la UI.

    Args:
        message: El último mensaje escrito por el usuario.
        history_list_gradio: El historial en formato Gradio [[user, assistant], ...]. Usado solo para display.
        history_state_agent: El historial en nuestro formato agente [{'role':..., 'content':...}] mantenido en gr.State.

    Returns:
        Una tupla: (nuevo_historial_agente_para_state, nuevo_historial_gradio_para_display)
    """
    agent_logger.info(f"Gradio UI -> Mensaje Usuario: '{message}'")
    if history_state_agent is None: # Primera interacción
        history_state_agent = []

    # Llamar a la lógica del agente que procesa un turno
    updated_agent_history, response_text = await process_agent_turn(
        user_input=message,
        history=history_state_agent,
        # Pasamos las instancias globales del agente y servidor MCP
        # ¡Importante! Asegúrate de que odoo_mcp_server se maneje correctamente de forma asíncrona
        # La función process_agent_turn ya lo maneja con 'async with' por ahora.
    )

    # Convertir el historial actualizado de formato agente a formato Gradio para mostrar
    gradio_display_history = []
    user_msg_for_pair = None
    for turn in updated_agent_history:
        role = turn.get("role")
        content = turn.get("content")

        if role == "user":
            user_msg_for_pair = content # Guardar mensaje de usuario para el par
        elif role == "assistant":
            # Extraer texto visible de la respuesta del asistente
            assistant_display_text = ""
            if isinstance(content, str):
                assistant_display_text = content
            elif isinstance(content, list): # Si content es una lista (puede incluir llamadas a tools)
                text_parts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                assistant_display_text = "\n".join(filter(None, text_parts)).strip()
                if not assistant_display_text and any(isinstance(part, dict) and part.get("type") == "tool_use" for part in content):
                     assistant_display_text = "(Realizando acciones con herramientas...)" # Placeholder si solo hubo tools
            elif isinstance(content, dict) and content.get("type") == "text": # Si es un simple bloque de texto
                 assistant_display_text = content.get("text", "")


            if user_msg_for_pair is not None:
                 gradio_display_history.append([user_msg_for_pair, assistant_display_text or "(No hubo respuesta textual)"])
                 user_msg_for_pair = None # Resetear para el próximo par
            else:
                 # Mensaje de asistente sin mensaje de usuario previo (ej. saludo inicial)
                 gradio_display_history.append([None, assistant_display_text or "(No hubo respuesta textual)"])

    # Si el último mensaje fue del usuario, añadirlo con respuesta None para Gradio
    if user_msg_for_pair is not None:
        gradio_display_history.append([user_msg_for_pair, None])


    agent_logger.info(f"Gradio UI -> Actualizando. Estado Agente: {len(updated_agent_history)} msgs. Display: {len(gradio_display_history)} pares.")
    # Devolvemos el nuevo estado (formato agente) y el historial para mostrar (formato gradio)
    return updated_agent_history, gradio_display_history

# --- Construcción de la Interfaz Gradio con Blocks ---
agent_logger.info("Construyendo la interfaz Gradio con gr.Blocks...")
with gr.Blocks(theme=gr.themes.Soft(), title="Asistente QuindíColor (Odoo + MCP + OpenAI)") as demo:
    gr.Markdown("# Asistente Inteligente QuindíColor")
    gr.Markdown("Interactúa con Odoo usando lenguaje natural. Prueba: 'Busca cliente X', 'Busca producto Y', 'Crea cotización para Z', 'Confirma cotización W'.")

    # Estado para mantener el historial en formato agente [{'role':..., 'content':...}]
    agent_history_state = gr.State([])

    # Componente de Chatbot para mostrar la conversación
    chatbot_display = gr.Chatbot(label="Conversación", height=500)

    # Componente Textbox para la entrada del usuario
    user_textbox = gr.Textbox(label="Tu Mensaje:", placeholder="Escribe aquí...")

    # Botón para limpiar el chat
    clear_button = gr.Button("Limpiar Chat")

    # Conectar el envío de mensaje (submit en Textbox o Enter) a la función handle_chat
    user_textbox.submit(
        handle_chat,
        inputs=[user_textbox, chatbot_display, agent_history_state], # Pasamos textbox, chatbot y state actual
        outputs=[agent_history_state, chatbot_display] # Recibimos nuevo state y contenido para chatbot
    )

    # Conectar el botón de limpiar
    clear_button.click(lambda: ([], [], []), None, [agent_history_state, chatbot_display, user_textbox], queue=False)

# --- Lanzar la aplicación Gradio ---
agent_logger.info("Lanzando la interfaz Gradio...")
print("Accede a la interfaz en la URL que aparecerá a continuación.")
# queue() es importante para manejar múltiples usuarios o llamadas largas
# share=True generaría un link público temporal (útil para demos rápidas, pero cuidado con la seguridad)
demo.queue().launch(share=False)

agent_logger.info("Interfaz Gradio cerrada.")