# app_gradio_voz.py (v9 - UI Alto Contraste Voz)

import gradio as gr
import asyncio
import logging
import os
import time
import tempfile

# Cliente OpenAI e Lógica del Agente
try:
    from openai import AsyncOpenAI
    oai_client = AsyncOpenAI()
    from agente_quindicolor_openai import agente_quindicolor, odoo_mcp_server, process_agent_turn, agent_logger
except ImportError:
    print("Error: Verifica 'openai' y 'agente_quindicolor_openai.py'.")
    exit(1)

# --- Funciones Auxiliares (STT, TTS) ---
async def transcribe_audio(filepath: str | None) -> str:
    if not filepath: return ""
    try:
        if not isinstance(filepath, str) or not os.path.exists(filepath): return "(Error: Archivo inválido)"
        with open(filepath, "rb") as audio_file:
            transcript = await oai_client.audio.transcriptions.create(model="whisper-1", file=audio_file)
        transcribed_text = transcript.text
        agent_logger.info(f"STT (Voz): Texto transcrito: '{transcribed_text}'")
        return transcribed_text if transcribed_text else "(Transcripción vacía)"
    except Exception as e:
        agent_logger.error(f"STT (Voz): Error Whisper: {e}", exc_info=True)
        return f"(Error transcripción: {type(e).__name__})"

async def text_to_speech(text: str) -> str | None:
    if not text or text.startswith("(") or text.strip() == "" or text == "(Acción interna realizada...)": return None
    try:
        temp_dir = tempfile.gettempdir()
        output_filename = f"gradio_tts_voz_{int(time.time()*1000)}.mp3"
        speech_file_path = os.path.join(temp_dir, output_filename)
        response = await oai_client.audio.speech.create(model="tts-1", voice="nova", input=text, response_format="mp3")
        await response.astream_to_file(speech_file_path)
        if os.path.exists(speech_file_path) and os.path.getsize(speech_file_path) > 0:
             agent_logger.info(f"TTS (Voz): Audio guardado en: {speech_file_path}")
             return speech_file_path
        else:
             agent_logger.error(f"TTS: Archivo TTS vacío o no creado en {speech_file_path}")
             return None
    except Exception as e:
        agent_logger.error(f"TTS (Voz): Error generando audio: {e}", exc_info=True)
        return None

# --- Lógica de Gradio para Voz ---
async def handle_voice_ui_update(audio_input_path: str | None, history_state_agent: list | None):
    agent_logger.info(f"handle_voice_ui_update recibido. Path: {audio_input_path}")
    if history_state_agent is None: history_state_agent = []

    transcribed_text = "(Esperando audio...)"
    tts_audio_path = None
    updated_agent_history = history_state_agent # Mantener el historial si hay error temprano

    # 1. Transcribir
    transcribed_text = await transcribe_audio(audio_input_path)

    # Si la transcripción fue exitosa y no está vacía
    if transcribed_text and not transcribed_text.startswith("("): # Asume que errores empiezan con '('
        agent_logger.info("STT exitosa, llamando al agente...")
        # 2. Llamar al agente
        updated_agent_history, response_text, _ = await process_agent_turn(
            user_input=transcribed_text,
            history=history_state_agent
        )
        # 3. Generar TTS
        tts_audio_path = await text_to_speech(response_text)
    elif audio_input_path: # Si hubo audio pero falló la transcripción/está vacío
         error_msg = transcribed_text or "(No se detectó audio o hubo un error al procesarlo)"
         agent_logger.warning(f"Problema con STT (Voz): {error_msg}")
         tts_audio_path = await text_to_speech(f"Hubo un error: {error_msg}")
         transcribed_text = f"INFO: {error_msg}" # Mostrar el error en texto
    else: # No se proporcionó audio
         transcribed_text = "(No se grabó audio)"

    agent_logger.info(f"Gradio Voz -> Turno completado. Texto STT: '{transcribed_text[:50]}...'. Path TTS: {tts_audio_path}")
    # Devolver: nuevo estado, texto transcrito para mostrar, path audio TTS
    return updated_agent_history, transcribed_text, tts_audio_path

# --- CSS para Alto Contraste (Tema Oscuro) ---
high_contrast_dark_css = """
body, .gradio-container { background-color: #1a1a1a !important; color: #e0e0e0 !important; font-family: 'Roboto', sans-serif; }
.gr-button { background-color: #505050; color: white; border: 1px solid #888; font-weight: bold; }
.gr-button:hover { background-color: #6a6a6a; border-color: #aaa;}
.gr-input input, .gr-input textarea, .gr-textbox, .gr-audio > div > audio { background-color: #2a2a2a !important; color: #e0e0e0 !important; border: 1px solid #555 !important; }
.gr-label > span, .gr-info, label span { color: #b0b0b0 !important; } /* Labels e info más claros */
.gr-markdown h2, .gr-markdown h3 { color: #ffffff; border-bottom: 1px solid #444; padding-bottom: 5px;}
.gr-markdown p, .gr-markdown li { color: #d0d0d0; line-height: 1.6;}
.gr-audio svg { fill: #cccccc !important; } /* Iconos de audio */
#component-0 { padding: 15px; background-color: #252525; border-radius: 8px; margin-bottom: 15px;} /* Contenedor principal */
.stt-output-box { background-color: #282828; border: 1px solid #444; padding: 10px; border-radius: 5px; min-height: 60px; } /* Caja para STT */
"""

# --- Construcción de la Interfaz Gradio (Solo Voz - UI Mejorada) ---
agent_logger.info("Construyendo interfaz Gradio (Solo Voz - UI Alto Contraste)...")
# Usamos el CSS personalizado
with gr.Blocks(css=high_contrast_dark_css, title="Asistente QuindíColor (Voz)") as demo_voz:
    gr.Markdown("## Asistente Inteligente QuindíColor (Interfaz de Voz)")
    gr.Markdown("Usa el micrófono para hablar con el asistente Odoo y escucha su respuesta.")

    agent_history_state_voz = gr.State([])

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("#### 🎤 Graba tu solicitud:")
            mic_input_voz = gr.Audio(sources=["microphone"], type="filepath", label=None)
            clear_button_voz = gr.Button("🗑️ Limpiar Conversación")

        with gr.Column(scale=2):
             gr.Markdown("#### ▶️ Lo que entendí (Transcripción):")
             # Usamos elem_classes para poder aplicar CSS si es necesario después
             stt_output_text = gr.Textbox(label=None, interactive=False, lines=3, elem_classes="stt-output-box")
             gr.Markdown("#### 🔊 Respuesta del Asistente:")
             audio_output_voz = gr.Audio(label=None, type="filepath", autoplay=True, interactive=False)

    # Conectar eventos
    mic_input_voz.stop_recording(
        handle_voice_ui_update,
        inputs=[mic_input_voz, agent_history_state_voz],
        outputs=[agent_history_state_voz, stt_output_text, audio_output_voz]
    )
    # Limpiar estado, texto STT y audio de salida
    clear_button_voz.click(lambda: ([], "", None), None, [agent_history_state_voz, stt_output_text, audio_output_voz], queue=False)

# --- Lanzar la aplicación ---
if __name__ == "__main__":
    agent_logger.info("Lanzando interfaz Gradio (Solo Voz - UI Alto Contraste)...")
    print("Accede a la interfaz de VOZ en la URL (Puerto 7860 por defecto):")
    demo_voz.queue().launch(server_name="0.0.0.0", server_port=7860)
    agent_logger.info("Interfaz Gradio (Voz) cerrada.")