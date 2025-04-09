# app_gradio_voz.py (v13 - Prueba Mic con Salida Texto)

import gradio as gr
import asyncio
import logging
import os
import time
from typing import List, Tuple # Añadido para type hints

# Logger simple
test_logger = logging.getLogger('gradio_mic_test_v13')
test_logger.setLevel(logging.INFO)
if not test_logger.handlers:
    test_console_handler = logging.StreamHandler()
    test_console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(test_console_handler)


# --- Handler SÍNCRONO de Prueba (Devuelve Texto) ---
def handle_voice_placeholder_text_out(audio_input_path: str | None, history_state: List | None) -> Tuple[List, str]:
    """Placeholder SÍNCRONO. Devuelve historial y un string para Textbox."""
    test_logger.info(f"Placeholder v13 recibió audio path: {audio_input_path}")
    if history_state is None: history_state = []

    response_text = "Placeholder: Micrófono parece funcionar."
    user_action_desc = "(No se grabó audio)"

    if audio_input_path and isinstance(audio_input_path, str) and os.path.exists(audio_input_path):
        try:
            file_size = os.path.getsize(audio_input_path)
            user_action_desc = f"Audio recibido ({file_size} bytes)"
            response_text = f"Placeholder: Procesado {user_action_desc}"
        except Exception as e:
             user_action_desc = f"Audio recibido (error tamaño: {e})"
             response_text = f"Placeholder: Error procesando audio - {e}"
    elif audio_input_path:
         user_action_desc = f"Audio recibido (path inválido: {audio_input_path})"
         response_text = f"Placeholder: Error - {user_action_desc}"
    
    # Actualizar historial (simulado)
    new_history = history_state + [
        {"role": "user", "content": user_action_desc},
        {"role": "assistant", "content": response_text}
    ]

    test_logger.info(f"Placeholder v13 devuelve historial (len {len(new_history)}) y texto: '{response_text}'")
    # Devolver historial actualizado y el texto de respuesta
    return new_history, response_text


# --- CSS (Opcional) ---
high_contrast_dark_css = """
body, .gradio-container { background-color: #1a1a1a !important; color: #e0e0e0 !important; }
.gr-button { background-color: #505050; color: white; border: 1px solid #888; }
/* ... */
"""

# --- Construcción Interfaz Gradio (Mic Input + Text Output + State) ---
test_logger.info("Construyendo interfaz Gradio MÍNIMA (Mic + State + Text Out)...")
with gr.Blocks(css=high_contrast_dark_css, title="Prueba Mic v13") as demo_mic_state_textout:
    gr.Markdown("## Prueba Final Mic: ¿Aparece el Micrófono?")
    gr.Markdown("Entrada de Micrófono, Salida de Texto, con Estado.")

    test_history_state = gr.State([])

    with gr.Column():
        mic_input = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Micrófono:")
        # --- CAMBIO PRINCIPAL: Salida es Textbox, no Audio ---
        output_placeholder_text = gr.Textbox(label="📄 Salida (Placeholder):", interactive=False, lines=3)
        clear_button = gr.Button("🗑️ Limpiar")

    # --- Conectar evento al HANDLER SÍNCRONO ---
    mic_input.stop_recording(
        handle_voice_placeholder_text_out,
        inputs=[mic_input, test_history_state],
        # Salidas: Actualizar estado y el textbox de salida
        outputs=[test_history_state, output_placeholder_text]
    )
    # Limpiar estado y texto de salida
    clear_button.click(lambda: ([], ""), None, [test_history_state, output_placeholder_text], queue=False)

# --- Lanzar la aplicación ---
if __name__ == "__main__":
    test_logger.info("Lanzando interfaz Gradio MÍNIMA (Mic + State + Text Out)...")
    print("Accede a la interfaz de prueba en la URL (Puerto 7860):")
    demo_mic_state_textout.launch(server_name="0.0.0.0", server_port=7860)
    test_logger.info("Interfaz Gradio MÍNIMA cerrada.")