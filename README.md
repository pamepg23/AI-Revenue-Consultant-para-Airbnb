# AI Revenue Consultant para Airbnb

## Descripción del proyecto

Este proyecto implementa una app de chat con sistema RAG para consultar documentos relacionados con estrategias de revenue management para Airbnb.

La aplicación permite hacer preguntas en lenguaje natural sobre documentos cargados en formato `.rtf`. El sistema recupera la información más relevante desde los documentos y genera una respuesta usando Gemini. Además, cada respuesta incluye las fuentes utilizadas, mostrando el nombre del documento de donde se extrajo la información.

El objetivo del proyecto es facilitar la consulta rápida de información sobre precios, temporadas, limpieza, errores en anuncios y recomendaciones para mejorar el desempeño de propiedades en Airbnb.

## Tecnologías utilizadas

- Python
- Google Colab
- Gradio
- LangChain
- Gemini 2.5 Flash / Gemini Flash
- Google Generative AI API
- GoogleGenerativeAIEmbeddings
- ChromaDB
- striprtf
- GitHub

## Funcionalidades principales

- Carga de documentos `.rtf` desde un repositorio de GitHub.
- Conversión de archivos RTF a texto.
- División de documentos en fragmentos usando LangChain.
- Creación de una base vectorial con ChromaDB.
- Generación de embeddings con Google Generative AI.
- Chat con Gradio usando `gr.ChatInterface`.
- Respuestas generadas con Gemini.
- Inclusión obligatoria de fuentes en cada respuesta.

## Instalación y ejecución local

### 1. Clonar el repositorio


### 2. Instalar dependencias

```bash
git clone https://github.com/pamepg23/AI-Revenue-Consultant-para-Airbnb.git
cd AI-Revenue-Consultant-para-Airbnb
```

### 2.  Instalar dependencias
pip install langchain langchain-google-genai langchain-chroma chromadb gradio langchain-text-splitters striprtf

3. Configurar API Key de Google
Debes tener una API key de Google AI Studio.

En Colab o en Python:

import os
from getpass import getpass

os.environ["GOOGLE_API_KEY"] = getpass("Pega tu GOOGLE_API_KEY: ")

4. Ejecutar el notebook
Abre el archivo .ipynb en Google Colab y ejecuta las celdas en orden:

Instalación de dependencias
Configuración de API key
Clonación del repositorio
Carga de documentos RTF
División de documentos
Creación de ChromaDB
Configuración de Gemini
Lanzamiento de la app Gradio

Link a la app desplegada
App desplegada:https://78b54bc1244f98475d.gradio.live/

Capturas de pantalla
Pantalla principal de la appß

