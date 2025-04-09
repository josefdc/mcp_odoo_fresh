# app_gradio_texto.py (v13 - Corregido NameError + UI Alto Contraste)

import gradio as gr
import asyncio
import logging
from typing import List, Dict, Any, Tuple

# Lógica del Agente
try:
    from agente_quindicolor_openai import (
        agente_quindicolor,
        odoo_mcp_server,
        process_agent_turn, # Usamos la versión SIN streaming
        agent_logger
    )
    # Función de conversión de historial
    def agent_history_to_gradio(agent_history: list) -> list:
            gradio_history = []
            user_msg_for_pair = None
            for turn in agent_history:
                role = turn.get("role"); content = turn.get("content"); content_str = ""
                if isinstance(content, str): content_str = content
                elif isinstance(content, list): text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type")=="text"]; content_str = "\n".join(filter(None, text_parts)).strip() or "(Acción con herramientas)"
                elif isinstance(content, dict) and content.get("type") == "text": content_str = content.get("text", "")
                elif role == "user": content_str = str(content)
                else: content_str = "(Respuesta no textual o compleja)"
                if role == "user": user_msg_for_pair = content_str
                elif role == "assistant":
                    if user_msg_for_pair is not None: gradio_history.append([user_msg_for_pair, content_str]); user_msg_for_pair = None
                    else: gradio_history.append([None, content_str])
            # No añadir el último user message aquí, Gradio lo maneja
            # if user_msg_for_pair is not None: gradio_history.append([user_msg_for_pair, None])
            return gradio_history

except ImportError:
    print("Error: No se pudo importar desde agente_quindicolor_openai.py.")
    exit(1)
except Exception as e:
     print(f"Error importando dependencias: {e}")
     exit(1)


# --- CSS para Alto Contraste ---
high_contrast_dark_css = """
body, .gradio-container { background-color: #1a1a1a !important; color: #e0e0e0 !important; font-family: 'Roboto', sans-serif; }
.gr-button { background-color: #505050; color: white; border: 1px solid #888; font-weight: bold; } .gr-button:hover { background-color: #6a6a6a; border-color: #aaa;} .gr-input input, .gr-input textarea, .gr-textbox { background-color: #2a2a2a !important; color: #e0e0e0 !important; border: 1px solid #555 !important; } .gr-chatbot { background-color: #252525 !important; } .gr-chatbot .message-bubble { border-radius: 15px; max-width: 90%; box-shadow: 1px 1px 3px rgba(0,0,0,0.3);} .gr-chatbot .message-bubble.user { background-color: #4a4e88 !important; color: white !important; border-bottom-right-radius: 5px !important; align-self: flex-end; } .gr-chatbot .message-bubble.bot { background-color: #383838 !important; color: #f0f0f0 !important; border-bottom-left-radius: 5px !important; align-self: flex-start; } .gr-label > span, label span { color: #b0b0b0 !important; } .gr-markdown h2, .gr-markdown h3 { color: #ffffff; border-bottom: 1px solid #444; padding-bottom: 5px;} .gr-markdown p, .gr-markdown li { color: #d0d0d0; line-height: 1.6;} .gradio-container .contain { gap: 0 !important; }
"""

# --- Lógica de Gradio para Texto (SIN Streaming) ---
async def handle_text_ui_update(text_message: str, history_state_agent: list | None):
    """Maneja input/output de texto con historial y chatbot (sin streaming)."""
    agent_logger.info(f"handle_text_ui_update recibido: '{text_message}'")
    if history_state_agent is None: history_state_agent = []

    if not text_message:
        agent_logger.warning("Input vacío (Texto).")
        return history_state_agent, agent_history_to_gradio(history_state_agent), ""

    # Llamar al agente (versión no-streaming)
    updated_agent_history, response_text, _ = await process_agent_turn(
        user_input=text_message,
        history=history_state_agent
    )

    # Convertir historial completo para display
    gradio_display_history = agent_history_to_gradio(updated_agent_history)

    agent_logger.info(f"Gradio Texto -> Turno procesado. Respuesta: '{response_text[:50]}...'. Historial: {len(updated_agent_history)} msgs.")
    return updated_agent_history, gradio_display_history, ""

# --- Construcción de la Interfaz Gradio ---
agent_logger.info("Construyendo interfaz Gradio (Solo Texto - UI Alto Contraste)...")
with gr.Blocks(css=high_contrast_dark_css, title="Asistente QuindíColor (Texto)") as demo_texto:
    gr.Markdown("## Asistente Inteligente QuindíColor (Interfaz de Texto)")
    gr.Markdown("Escribe tu solicitud para interactuar con Odoo.")

    agent_history_state_texto = gr.State([])

    with gr.Column():
        chatbot_display_texto = gr.Chatbot(
            label="Conversación", height=600, bubble_full_width=False,
            avatar_images=(None, "https://www.google.com/s2/favicons?domain=openai.com&sz=64")
        )
        text_input_texto = gr.Textbox(
            label="Escribe aquí:", placeholder="Ej: Busca cliente ACME...", show_label=False
        )
        clear_button_texto = gr.Button("🗑️ Limpiar Chat")

    # --- Conectar Eventos ---
    text_input_texto.submit(
        handle_text_ui_update,
        inputs=[text_input_texto, agent_history_state_texto],
        outputs=[agent_history_state_texto, chatbot_display_texto, text_input_texto]
    )
    clear_button_texto.click(lambda: ([], [], ""), None, [agent_history_state_texto, chatbot_display_texto, text_input_texto], queue=False)

# --- Lanzar la aplicación ---
if __name__ == "__main__":
    # La validación de la API Key la maneja la librería openai o la lógica importada
    agent_logger.info("Lanzando interfaz Gradio (Solo Texto - UI Alto Contraste)...")
    print("Accede a la interfaz de TEXTO en la URL (Puerto 7861 por defecto):")
    demo_texto.queue().launch(server_name="0.0.0.0", server_port=7861)
    agent_logger.info("Interfaz Gradio (Texto) cerrada.")