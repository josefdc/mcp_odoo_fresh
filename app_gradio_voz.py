# app_gradio.py (v6 - Corregido Error 'info' en gr.Audio)

import gradio as gr
import asyncio
import logging
import tempfile
import os
import time

# Cliente OpenAI (asume variable de entorno OPENAI_API_KEY)
try:
    from openai import AsyncOpenAI
    oai_client = AsyncOpenAI()
except ImportError:
    print("Error: La librería 'openai' no está instalada. Ejecuta: uv pip install openai")
    exit(1)

# Lógica del Agente (importar funciones/variables necesarias)
try:
    from agente_quindicolor_openai import (
        agente_quindicolor,
        odoo_mcp_server,
        process_agent_turn,
        agent_logger
    )
except ImportError:
    print("Error: No se pudo importar desde agente_quindicolor_openai.py.")
    exit(1)

# --- Lógica de Transcripción (STT - igual que antes) ---
async def transcribe_audio(filepath: str | None) -> str:
    """Transcribe un archivo de audio usando OpenAI Whisper."""
    if not filepath:
        agent_logger.warning("No se proporcionó archivo de audio para transcribir.")
        return ""
    try:
        agent_logger.info(f"Transcribiendo archivo de audio: {filepath}")
        if not isinstance(filepath, str) or not os.path.exists(filepath):
             agent_logger.error(f"Path de audio inválido/no existe: {filepath}")
             return "(Error: Archivo de audio inválido)"

        with open(filepath, "rb") as audio_file:
            transcript = await oai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        transcribed_text = transcript.text
        agent_logger.info(f"Texto transcrito: '{transcribed_text}'")
        return transcribed_text if transcribed_text else "(Transcripción vacía)"
    except Exception as e:
        agent_logger.error(f"Error durante transcripción Whisper: {e}", exc_info=True)
        return f"(Error en transcripción: {type(e).__name__})"

# --- Lógica de Texto a Voz (TTS - igual que antes) ---
async def text_to_speech(text: str) -> str | None:
    """Convierte texto a audio MP3 usando OpenAI TTS y devuelve la ruta a un archivo temporal."""
    if not text or text.startswith("(") or text.strip() == "":
        agent_logger.warning(f"No se generará TTS para texto vacío o de error: '{text}'")
        return None
    try:
        agent_logger.info(f"Generando TTS para: '{text[:50]}...'")
        temp_dir = tempfile.gettempdir()
        output_filename = f"gradio_tts_output_{int(time.time()*1000)}.mp3"
        speech_file_path = os.path.join(temp_dir, output_filename)

        response = await oai_client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="mp3"
        )
        await response.astream_to_file(speech_file_path)
        agent_logger.info(f"Audio TTS guardado en: {speech_file_path}")
        return speech_file_path
    except Exception as e:
        agent_logger.error(f"Error durante generación TTS: {e}", exc_info=True)
        return None

# --- Lógica de la Interfaz Gradio (Adaptada para TTS) ---
async def handle_audio_input_with_tts(audio_input_path: str | None, history_state_agent: list | None):
    """
    Maneja entrada de audio, transcribe, llama al agente, genera TTS y devuelve ruta de audio y estado.
    """
    agent_logger.info(f"handle_audio_input_with_tts recibido. Path: {audio_input_path}")
    if history_state_agent is None:
        history_state_agent = []

    # 1. Transcribir
    user_text = await transcribe_audio(audio_input_path)
    # IMPORTANTE: Añadir el texto transcrito (si es válido) al historial ANTES de llamar al agente
    if user_text and not user_text.startswith("(Error"):
        history_state_agent.append({"role": "user", "content": user_text})
    elif audio_input_path: # Si hubo audio pero falló la transcripción
         error_msg = user_text or "(No se detectó audio o hubo un error al procesarlo)"
         agent_logger.warning(f"Problema con audio/transcripción: {error_msg}")
         # Devolver historial sin cambios y None para el audio (sin respuesta de voz)
         # Añadir un mensaje de error visible sería bueno, pero complicaría el return
         return history_state_agent, None # Simplificado: no hay audio de respuesta
    else: # No hubo input de audio
         return history_state_agent, None


    # 2. Llamar al agente con el historial que YA incluye el último input del usuario
    # Nota: pasamos history_state_agent directamente porque ya lo actualizamos
    updated_agent_history, response_text = await process_agent_turn(
        # user_input ya no se pasa aquí, va dentro del historial
        user_input=user_text, # AUNQUE process_agent_turn lo añade de nuevo, revisar esa lógica
        history=history_state_agent[:-1] # Pasar historial SIN el último input añadido arriba
                                        # Corrección: process_agent_turn espera el historial *antes* del último input
                                        # y el input por separado. ¡Hay que ajustar eso!
                                        # -> Ajustaremos process_agent_turn para aceptar solo historial y añadir el input dentro
                                        # -> O ajustamos aquí para no añadir user_text a history_state_agent todavía
                                        # -> Vamos a ajustar aquí por simplicidad ahora:
                                        # NO añadimos user_text a history_state_agent aquí.
                                        # process_agent_turn lo hará.
    )
    # La función process_agent_turn devuelve el historial YA actualizado con user y assistant
    history_state_agent = updated_agent_history # Actualizamos el state con lo devuelto

    # 3. Generar TTS a partir de la respuesta de texto del agente
    tts_audio_path = await text_to_speech(response_text)

    agent_logger.info(f"Gradio UI (TTS) -> Respuesta Texto: '{response_text[:70]}...'. Path Audio TTS: {tts_audio_path}. Nuevo historial: {len(history_state_agent)} msgs.")
    # Devolver el nuevo estado del historial y la RUTA al archivo de audio TTS
    return history_state_agent, tts_audio_path


# --- Construcción de la Interfaz Gradio con Blocks (con Salida de Audio) ---
agent_logger.info("Construyendo la interfaz Gradio con Salida de Audio...")
# Eliminado el argumento 'theme'
with gr.Blocks(title="Asistente QuindíColor (Voz)") as demo:
    gr.Markdown("# Asistente Inteligente QuindíColor (Voz)")
    gr.Markdown("Usa el micrófono para hablar con el asistente Odoo y escucha su respuesta.")

    # Estado para mantener el historial en formato agente
    agent_history_state = gr.State([]) # Inicializado como lista vacía

    # --- ENTRADA DE AUDIO (Corregido: sin 'info') ---
    mic_input = gr.Audio(sources=["microphone"], type="filepath", label="Habla aquí:")

    # --- SALIDA DE AUDIO ---
    audio_output = gr.Audio(label="Respuesta del Agente:", type="filepath", autoplay=True)

    # Botón para limpiar
    clear_button = gr.Button("Limpiar")

    # Conectar la DETENCIÓN de la grabación a la función con TTS
    mic_input.stop_recording(
        handle_audio_input_with_tts,
        # Inputs: el componente de audio y el estado del historial
        inputs=[mic_input, agent_history_state],
        # Outputs: actualizar el estado y el componente de audio de salida
        outputs=[agent_history_state, audio_output]
    )

    # Conectar el botón de limpiar
    clear_button.click(lambda: ([], None), None, [agent_history_state, audio_output], queue=False)

# --- Lanzar la aplicación Gradio ---
agent_logger.info("Lanzando la interfaz Gradio con TTS...")
print("Accede a la interfaz en la URL que aparecerá a continuación.")
demo.queue().launch(share=False)
agent_logger.info("Interfaz Gradio cerrada.")