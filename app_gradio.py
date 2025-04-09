# app_gradio.py (v7 - Doble Entrada + Chatbot + TTS)

import gradio as gr
import asyncio
import logging
import tempfile
import os
import time

# Cliente OpenAI
try:
    from openai import AsyncOpenAI
    oai_client = AsyncOpenAI()
except ImportError:
    print("Error: 'openai' no instalada.")
    exit(1)

# Lógica del Agente
try:
    from agente_quindicolor_openai import (
        agente_quindicolor,
        odoo_mcp_server,
        process_agent_turn, # La función refactorizada
        agent_logger
    )
except ImportError:
    print("Error importando desde agente_quindicolor_openai.py.")
    exit(1)

# --- Funciones Auxiliares (STT, TTS, Conversión Historial) ---

async def transcribe_audio(filepath: str | None) -> str:
    # (Misma función que antes)
    if not filepath: return ""
    try:
        if not isinstance(filepath, str) or not os.path.exists(filepath): return "(Error: Archivo inválido)"
        with open(filepath, "rb") as audio_file:
            transcript = await oai_client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        return transcript.text if transcript.text else "(Transcripción vacía)"
    except Exception as e:
        agent_logger.error(f"Error Whisper: {e}", exc_info=True)
        return f"(Error transcripción: {type(e).__name__})"

async def text_to_speech(text: str) -> str | None:
    # (Misma función que antes)
    if not text or text.startswith("(") or text.strip() == "": return None
    try:
        temp_dir = tempfile.gettempdir()
        output_filename = f"gradio_tts_output_{int(time.time()*1000)}.mp3"
        speech_file_path = os.path.join(temp_dir, output_filename)
        response = await oai_client.audio.speech.create(model="tts-1", voice="nova", input=text, response_format="mp3")
        await response.astream_to_file(speech_file_path)
        return speech_file_path
    except Exception as e:
        agent_logger.error(f"Error TTS: {e}", exc_info=True)
        return None

def agent_history_to_gradio(agent_history: list) -> list:
    """Convierte historial agente [{'role':..}] a formato Gradio [[user, assist],..]."""
    gradio_history = []
    user_msg_for_pair = None
    for turn in agent_history:
        role = turn.get("role")
        content = turn.get("content")
        # Simplificar: asumimos que 'content' es string para este ejemplo
        # Una versión robusta necesitaría parsear la estructura compleja de 'content' del asistente
        content_str = str(content)
        # Para mostrar el texto del asistente, podríamos necesitar extraerlo si es complejo
        if role == 'assistant':
             if isinstance(content, list): # Si es lista de bloques
                  text_parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type")=="text"]
                  content_str = "\n".join(filter(None, text_parts)).strip()
                  if not content_str and any(isinstance(p, dict) and p.get("type") == "tool_use" for p in content):
                       content_str = "(Realizando acción...)" # Placeholder
             elif isinstance(content, dict) and content.get("type") == "text":
                  content_str = content.get("text", "(Respuesta sin texto)")
             elif not isinstance(content, str):
                  content_str = "(Respuesta no textual)" # Placeholder general

        if role == "user":
            user_msg_for_pair = content_str
        elif role == "assistant":
            if user_msg_for_pair is not None:
                gradio_history.append([user_msg_for_pair, content_str])
                user_msg_for_pair = None
            else: # Mensaje inicial del asistente?
                 gradio_history.append([None, content_str])
    # Añadir último mensaje de usuario si quedó pendiente
    if user_msg_for_pair is not None:
         gradio_history.append([user_msg_for_pair, None])
    return gradio_history

# --- Lógica Principal de Gradio ---

# Función núcleo que maneja un turno, independientemente de si vino de texto o voz
async def handle_turn_core(user_text: str, history_state_agent: list | None):
    if history_state_agent is None: history_state_agent = []
    if not user_text or user_text.startswith("(Error"):
        error_msg = user_text or "(Input vacío o inválido)"
        agent_logger.warning(f"Input inválido para procesar: {error_msg}")
        # Devolver historial sin cambios, historial display con error, sin audio
        return history_state_agent, agent_history_to_gradio(history_state_agent + [{"role":"assistant", "content":error_msg}]), None

    # Llamar al agente
    updated_agent_history, response_text, _ = await process_agent_turn(
        user_input=user_text,
        history=history_state_agent # Pasamos historial ANTES del input actual
    )

    # Generar TTS
    tts_audio_path = await text_to_speech(response_text)

    # Convertir historial para display
    gradio_display_history = agent_history_to_gradio(updated_agent_history)

    return updated_agent_history, gradio_display_history, tts_audio_path


# Funciones wrapper para los eventos de Gradio

async def handle_text_input(text_message: str, history_state_agent: list | None):
    agent_logger.info("Evento: Texto enviado.")
    # El último elemento del historial display será el input de texto, lo añadimos al state
    # Nota: Gradio Chatbot no pasa el historial en el input, usamos el state
    # if history_state_agent is None: history_state_agent = []

    updated_state, display_hist, audio_path = await handle_turn_core(text_message, history_state_agent)
    # Devolvemos el nuevo estado, el historial para el chatbot, y la ruta del audio TTS
    # También limpiamos la caja de texto
    return updated_state, display_hist, audio_path, "" # Limpiar textbox


async def handle_audio_input(audio_path: str | None, history_state_agent: list | None):
    agent_logger.info("Evento: Audio grabado.")
    if audio_path is None:
         return history_state_agent, agent_history_to_gradio(history_state_agent), None # No hacer nada si no hay audio

    transcribed_text = await transcribe_audio(audio_path)
    # Llamar a la lógica central con el texto transcrito
    updated_state, display_hist, audio_path = await handle_turn_core(transcribed_text, history_state_agent)
    # Devolvemos el nuevo estado, el historial para el chatbot, y la ruta del audio TTS
    return updated_state, display_hist, audio_path


# --- Construcción de la Interfaz Gradio ---
agent_logger.info("Construyendo la interfaz Gradio completa...")
with gr.Blocks(theme=gr.themes.Soft(), title="Asistente QuindíColor") as demo: # Usamos Soft theme
    gr.Markdown("## Asistente Inteligente QuindíColor (Odoo + MCP + OpenAI + Voz)")
    gr.Markdown("Interactúa escribiendo o usando el micrófono.")

    # Estado para el historial (formato agente)
    agent_history_state = gr.State([])

    with gr.Row():
        with gr.Column(scale=3):
             # Salida principal: el chatbot
            chatbot_display = gr.Chatbot(label="Conversación", height=550, bubble_full_width=False)

             # Salida de audio TTS
            audio_output = gr.Audio(label="Respuesta (Voz)", type="filepath", autoplay=True, interactive=False)

        with gr.Column(scale=1):
            gr.Markdown("### Entradas")
            # Entrada de texto
            text_input = gr.Textbox(label="Escribe tu mensaje:", placeholder="Ej: Busca cliente ACME...")
            # Entrada de audio
            mic_input = gr.Audio(sources=["microphone"], type="filepath", label="O habla aquí:")
            # Botón Limpiar
            clear_button = gr.Button("🗑️ Limpiar Chat")


    # --- Conexiones de Eventos ---

    # Al enviar texto (Enter en Textbox)
    text_input.submit(
        handle_text_input,
        inputs=[text_input, agent_history_state],
        outputs=[agent_history_state, chatbot_display, audio_output, text_input] # Actualiza state, chatbot, audio y limpia textbox
    )

    # Al detener grabación del micrófono
    mic_input.stop_recording(
        handle_audio_input,
        inputs=[mic_input, agent_history_state],
        outputs=[agent_history_state, chatbot_display, audio_output] # Actualiza state, chatbot y audio
    )

    # Al hacer clic en Limpiar
    clear_button.click(lambda: ([], [], None, ""), None, [agent_history_state, chatbot_display, audio_output, text_input], queue=False)


# --- Lanzar la aplicación ---
agent_logger.info("Lanzando la interfaz Gradio completa...")
print("Accede a la interfaz en la URL que aparecerá a continuación.")
demo.queue().launch(share=False)
agent_logger.info("Interfaz Gradio cerrada.")