# test_mic_with_state.py
import gradio as gr
import os
import time
from typing import List, Tuple # Necesario para type hints

print("Construyendo interfaz de prueba de micrófono Gradio CON ESTADO...")

# Función de procesamiento (síncrona), ahora recibe y devuelve el estado
def process_audio_with_state(audio_filepath: str | None, current_history: List | None) -> Tuple[List, str]:
    print(f"Timestamp: {time.time()}")
    print(f"Callback 'process_audio_with_state' recibió audio: {audio_filepath}")
    print(f"Historial de estado recibido (longitud): {len(current_history) if current_history else 0}")

    if current_history is None:
        current_history = []

    text_output = ""
    if audio_filepath and isinstance(audio_filepath, str) and os.path.exists(audio_filepath):
        try:
            file_size = os.path.getsize(audio_filepath)
            print(f"El archivo existe. Tamaño: {file_size} bytes")
            text_output = f"Audio recibido ({file_size} bytes). Path: {audio_filepath}"
            # Simular añadir algo al historial
            current_history.append({"user_input_type": "audio", "path": audio_filepath, "result": text_output})
        except Exception as e:
             print(f"Error al obtener tamaño del archivo: {e}")
             text_output = f"Audio recibido, pero error al leer tamaño: {e}"
             current_history.append({"user_input_type": "audio", "path": audio_filepath, "error": text_output})

    elif audio_filepath:
        print(f"Se recibió la ruta '{audio_filepath}' pero el archivo NO existe.")
        text_output = f"Error: Gradio pasó ruta pero archivo no encontrado: {audio_filepath}"
        current_history.append({"user_input_type": "audio", "path": audio_filepath, "error": text_output})
    else:
        print("No se recibió ruta de archivo de audio.")
        text_output = "No se grabó o no se recibió audio."
        # No añadir al historial si no hubo input

    print(f"Devolviendo nuevo historial (longitud {len(current_history)}) y texto: '{text_output}'")
    # Devolver el historial actualizado y el texto de salida
    return current_history, text_output

# Construir UI con gr.Blocks
with gr.Blocks(title="Prueba Mic + State") as demo_state_test:
    gr.Markdown("# Prueba Simple de Micrófono Gradio + Estado")
    gr.Markdown("Intenta grabar algo. ¿Aparece el micrófono?")

    # 1. Añadir el componente de Estado
    history_state = gr.State([])

    # 2. Componente de Audio (igual que antes)
    mic_input = gr.Audio(sources=["microphone"], type="filepath", label="Grabación:")

    # 3. Componente de Texto para salida (igual que antes)
    output_text = gr.Textbox(label="Resultado del Callback")

    # 4. Conectar evento stop_recording
    mic_input.stop_recording(
        fn=process_audio_with_state, # Usar la nueva función
        inputs=[mic_input, history_state], # Pasar audio y estado
        outputs=[history_state, output_text] # Actualizar estado y texto
    )

    # (Opcional: Botón para ver el estado)
    # state_display = gr.JSON(label="Historial Interno (Estado)")
    # show_state_btn = gr.Button("Mostrar Estado")
    # show_state_btn.click(lambda s: s, inputs=[history_state], outputs=[state_display])

print("Lanzando demo de micrófono con estado...")
demo_state_test.launch() # Sin queue para simplicidad
print("Demo cerrada.")