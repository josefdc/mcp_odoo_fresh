# Agente Inteligente QuindíColor: Odoo + MCP + OpenAI

## Proyecto Hackathon 🚀

Este proyecto, desarrollado para una hackathon, demuestra la creación de un agente conversacional inteligente capaz de interactuar con un sistema ERP Odoo (específicamente una instancia alojada en Odoo.sh) para realizar tareas clave del flujo de ventas de la empresa ficticia "QuindíColor".

El agente utiliza el **SDK de OpenAI Agents** para su lógica y razonamiento, se comunica mediante **voz o texto** a través de interfaces web interactivas creadas con **Gradio**, y, de manera crucial, accede a las funcionalidades de Odoo de forma estandarizada y desacoplada gracias al **Model Context Protocol (MCP)**.

**Objetivo Principal:** Simplificar y agilizar operaciones comunes de ventas en Odoo (buscar clientes/productos, crear y confirmar cotizaciones) mediante una interfaz conversacional avanzada (texto y voz), resaltando la flexibilidad que aporta MCP.

## Tecnologías Utilizadas 🛠️

* **Python:** Lenguaje principal de programación (v3.10+ recomendado).
* **Odoo (Odoo.sh):** Sistema ERP de destino donde residen los datos y se ejecutan las acciones comerciales.
* **Model Context Protocol (MCP):** Protocolo estándar utilizado para la comunicación entre el agente inteligente y el servidor que expone las capacidades de Odoo. Se implementa un servidor MCP personalizado.
    * Se usa el SDK `mcp` para Python (`pip install mcp`).
* **OpenAI Agents SDK:** Framework para construir la lógica del agente, manejar el flujo conversacional y la integración con herramientas MCP (`pip install openai-agents`).
* **OpenAI API:**
    * **LLM (GPT-4o):** Para el razonamiento del agente, comprensión del lenguaje natural y selección de herramientas.
    * **Whisper:** Para la transcripción de Voz a Texto (STT).
    * **TTS API:** Para la síntesis de Texto a Voz (TTS).
    * Se requiere la librería `openai` (`pip install openai`).
* **Gradio:** Framework para crear rápidamente las interfaces web interactivas de chat y voz (`pip install gradio`).
* **Odoo API (XML-RPC):** Método de comunicación específico utilizado por nuestro servidor MCP para interactuar con la API externa de Odoo.
* **uv:** Gestor de paquetes y entornos virtuales Python (`pip install uv`).
* **python-dotenv:** Para gestionar credenciales y configuraciones de entorno de forma segura.

## Arquitectura del Sistema 🏛️

El sistema conecta al usuario con Odoo a través de varias capas, donde MCP juega un papel central como puente estandarizado.

<!-- Reemplaza esto con la imagen real cuando esté disponible -->
<!-- ![Arquitectura Simplificada](architecture.png) -->

**Flujo Típico:**

1. El **Usuario** interactúa (voz/texto) con la **Interfaz Gradio**.
2. La **App Backend (Gradio + Python)** recibe el input. Si es voz, llama a la **API Whisper (STT)** de OpenAI para transcribir.
3. El texto (transcrito o escrito) se pasa a la **Lógica del Agente (OpenAI Agents SDK)** junto con el historial.
4. El Agente llama al **LLM (GPT-4o)** de OpenAI con el prompt, historial y la lista de herramientas disponibles (descubiertas vía MCP).
5. El LLM decide si responder directamente o usar una herramienta.
6. Si decide usar una herramienta Odoo (ej. `buscar_cliente`):
    * La Lógica del Agente instruye al **Conector MCP** (`MCPServerStdio`).
    * El Conector MCP envía una petición `tools/call` usando el **Protocolo MCP** a nuestro **Servidor MCP Odoo** (`mcp_odoo_server.py`), que corre como proceso hijo.
    * Nuestro Servidor MCP traduce la petición MCP a una llamada **XML-RPC** a la **API de Odoo.sh**.
    * **Odoo.sh** procesa la solicitud y devuelve el resultado vía XML-RPC.
    * Nuestro Servidor MCP recibe la respuesta de Odoo y la formatea como un **Resultado MCP**.
    * El Conector MCP recibe el resultado y lo devuelve a la Lógica del Agente.
    * El Agente envía el resultado de la herramienta de nuevo al **LLM** para generar la respuesta final al usuario.
7. La Lógica del Agente recibe la respuesta final en texto del LLM.
8. La App Backend llama a la **API TTS** de OpenAI para convertir el texto en audio (si es la interfaz de voz).
9. La App Backend actualiza la **Interfaz Gradio** mostrando el texto en el chat y/o reproduciendo el audio.
10. El **Usuario** ve/escucha la respuesta.

**Importancia del Model Context Protocol (MCP):**

MCP es la **clave** para la integración flexible y modular en este proyecto:

* **Estandarización:** Define un contrato claro (`list_tools`, `call_tool`) entre el agente y las capacidades de Odoo. El agente no necesita saber *cómo* hablar XML-RPC con Odoo, solo cómo usar las herramientas MCP.
* **Desacoplamiento:** La inteligencia del agente (OpenAI SDK) está separada de la implementación específica de Odoo (nuestro servidor MCP). Podemos cambiar el agente o el servidor Odoo (ej. a otra versión de Odoo o API) modificando solo una parte, siempre que se respete el contrato MCP.
* **Reusabilidad:** Nuestro `mcp_odoo_server.py` podría ser utilizado por *cualquier* otro sistema o agente que entienda MCP, no solo por el SDK de OpenAI Agents.
* **Modularidad:** Permite exponer funcionalidades de sistemas complejos (como Odoo) de forma granular y controlada (herramienta por herramienta).

MCP actúa como una **capa de abstracción esencial**, permitiendo que sistemas inteligentes interactúen con herramientas y datos de forma estandarizada y segura.

## Estructura del Proyecto 📂

```
mcp_odoo_fresh/
├── .venv/                      # Entorno virtual Python (creado por uv)
├── agente_quindicolor_openai.py # Lógica del Agente OpenAI, configuración MCP
├── app_gradio_texto.py        # Interfaz Gradio para chat de texto
├── app_gradio_voz.py          # Interfaz Gradio para chat de voz (STT/TTS)
├── mcp_odoo_server.py         # Servidor MCP -> Odoo (FastMCP, XML-RPC)
├── mcp_odoo_debug.log         # Archivo de log del servidor MCP Odoo
├── .env                       # Archivo para credenciales (¡IGNORADO POR GIT!)
├── .env.example               # Archivo de ejemplo para .env
├── pyproject.toml             # Configuración del proyecto (usado por uv)
├── README.md                  # Este archivo
└── uv.lock                    # Dependencias bloqueadas por uv
```

## Instrucciones de Configuración 🛠️

1. **Clonar/Descargar:** Obtén los archivos del proyecto.
2. **Prerrequisitos:**
    * Python 3.10 o superior.
    * `uv` instalado (ver [guía oficial](https://astral.sh/uv/install.sh)).
    * Acceso a una instancia de Odoo (preferiblemente Odoo.sh) con un usuario y Clave API.
    * Una Clave API de OpenAI con crédito/cuota suficiente.
3. **Crear y Activar Entorno Virtual:**
    ```bash
    cd ruta/a/mcp_odoo_fresh
    uv venv
    source .venv/bin/activate # Linux/macOS
    # .venv\Scripts\activate # Windows
    ```
4. **Instalar Dependencias:**
    ```bash
    uv pip install openai-agents openai python-dotenv gradio mcp
    ```
    *(Puedes también crear un `requirements.txt` con `uv pip freeze > requirements.txt` y luego usar `uv pip install -r requirements.txt`)*.
5. **Configurar Credenciales:**
    * Renombra o copia `.env.example` a `.env`.
    * Edita el archivo `.env` y rellena **TODAS** las variables con tus valores reales:
        ```
        # === Credenciales Odoo.sh ===
        ODOO_URL=https://tu-instancia.odoo.com
        ODOO_DB=nombre_tu_base_de_datos
        ODOO_USER=tu_login_odoo
        ODOO_PASSWORD=TU_CLAVE_API_DE_ODOO_SH # ¡Generada en Odoo.sh!

        # === Credenciales OpenAI ===
        OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
        ```

## Ejecución de la Demo ▶️

Puedes ejecutar la interfaz de texto o la de voz de forma independiente. Ambas iniciarán el servidor MCP Odoo necesario en segundo plano.

**Opción 1: Interfaz de Texto**

```bash
python app_gradio_texto.py
```

Abre la URL que indica la consola (normalmente http://127.0.0.1:7861).

**Opción 2: Interfaz de Voz**

```bash
python app_gradio_voz.py
```

Abre la URL que indica la consola (normalmente http://127.0.0.1:7860). Recuerda dar permiso al navegador para usar el micrófono.

## Guiones de Prueba

Puedes usar los guiones proporcionados anteriormente (adaptados a tus productos/clientes) para probar el flujo completo en cualquiera de las interfaces.

## Troubleshooting Básico 🐛

* **Error Odoo:** Revisa URL, DB, User, Password (API Key!) en .env. Mira mcp_odoo_debug.log.
* **Error OpenAI:** Verifica tu API Key y cuota en platform.openai.com.
* **Error Gradio (Micrófono):** Revisa permisos del navegador/OS. Usa URL local. Prueba otro navegador.
* **Otros:** Revisa los logs en la terminal donde ejecutas la app Gradio.

## Ideas Futuras 💡

* Implementar la herramienta crear_factura_desde_pedido (requiere investigar método Odoo no privado).
* Añadir más herramientas (ej. consultar stock, estado pedido).
* Mejorar el manejo de errores y la robustez.
* Implementar streaming de texto en la interfaz de voz.
* Optimizar el arranque/conexión del servidor MCP.
* Usar un gr.Chatbot visible en la app de voz para mostrar historial

este proyecto nos hizo ganadores jeje 