# test_mic.py
import gradio as gr
import os
import time

def process_audio(audio_filepath):
    print(f"Timestamp: {time.time()}")
    print(f"Callback 'process_audio' recibió: {audio_filepath}")
    if audio_filepath and isinstance(audio_filepath, str) and os.path.exists(audio_filepath):
        try:
            file_size = os.path.getsize(audio_filepath)
            print(f"El archivo existe. Tamaño: {file_size} bytes")
            return f"Audio recibido ({file_size} bytes). Path: {audio_filepath}"
        except Exception as e:
             print(f"Error al obtener tamaño del archivo: {e}")
             return f"Audio recibido, pero error al leer tamaño: {e}"
    elif audio_filepath:
        print(f"Se recibió la ruta '{audio_filepath}' pero el archivo NO existe.")
        return f"Error: Gradio pasó una ruta pero el archivo no se encontró: {audio_filepath}"
    else:
        print("No se recibió ruta de archivo de audio.")
        return "No se grabó o no se recibió audio."

print("Construyendo interfaz de prueba de micrófono Gradio...")
with gr.Blocks(title="Prueba Micrófono") as demo:
    gr.Markdown("# Prueba Simple de Micrófono Gradio")
    gr.Markdown("Intenta grabar algo usando el micrófono de abajo.")
    # Definimos el componente de Audio para usar el micrófono
    mic_input = gr.Audio(sources=["microphone"], type="filepath", label="Grabación:")
    output_text = gr.Textbox(label="Resultado del Callback")

    # Conectamos el evento 'stop_recording' a nuestra función
    mic_input.stop_recording(
        fn=process_audio,
        inputs=[mic_input],
        outputs=[output_text]
    )

print("Lanzando demo de micrófono...")
# Lanzamos sin cola para simplificar la prueba inicial
demo.launch()
print("Demo cerrada.")