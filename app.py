import glob
import os
import gradio as gr
import time
from typing import Any
from striprtf.striprtf import rtf_to_text
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import traceback


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("Falta configurar GOOGLE_API_KEY como Secret en Hugging Face.")


# =========================
# Configuración general
# =========================
RTF_FOLDER = "documents"

MODEL_NAME = "gemini-2.5-flash"
EMBEDDING_MODEL = "models/gemini-embedding-001"

CHUNK_SIZE = 700
CHUNK_OVERLAP = 100
TOP_K = 2

def limpiar_texto(texto: str | None) -> str:
    """Limpia y normaliza texto extraído desde archivos RTF.
    Args:
        texto: Texto original extraído del documento RTF. Puede ser None.
    Returns:
        Texto limpio, codificado en UTF-8 y sin caracteres nulos.
    """
    if texto is None:
        return ""

    texto = texto.encode("utf-8", "ignore").decode("utf-8", "ignore")
    texto = texto.replace("\x00", " ")
    texto = " ".join(texto.split())

    return texto

# =========================
# Cargar documentos RTF
# =========================
rtf_files = sorted(glob.glob(os.path.join(RTF_FOLDER, "**/*.rtf"), recursive=True))

print(f"Archivos .rtf encontrados: {len(rtf_files)}")

for file in rtf_files:
    print("-", file)

if len(rtf_files) < 1:
    raise ValueError("No se encontraron archivos .rtf en la carpeta documents.")

documents = []

for file_path in rtf_files:
    try:
        print(f"Leyendo archivo: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            rtf_content = f.read()

        text = rtf_to_text(rtf_content)
        text = limpiar_texto(text)

        if not text.strip():
            print(f"Documento vacío después de limpiar, se omite: {file_path}")
            continue

        source_name = os.path.basename(file_path)

        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": source_name,
                    "path": file_path
                }
            )
        )

    except Exception as e:
        print(f"Error leyendo el archivo {file_path}: {e}")

    finally:
        print(f"Proceso terminado para: {file_path}")
        
if len(documents) < 1:
    raise ValueError("No se pudo cargar ningún documento válido.")      


# =========================
# Dividir documentos
# =========================
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ".", " ", ""]
)

chunks = text_splitter.split_documents(documents)

print(f"Chunks creados: {len(chunks)}")

if len(chunks) < 1:
    raise ValueError("No se crearon chunks. Revisa el contenido de los documentos.")

# =========================
# Crear ChromaDB en memoria
# =========================

embeddings = GoogleGenerativeAIEmbeddings(
    model=EMBEDDING_MODEL
)

def crear_vectorstore_con_reintentos(
    chunks: list[Document],
    max_intentos: int = 5
) -> Chroma:
    """Crea una base vectorial ChromaDB en memoria con reintentos.
    Args:
        chunks: Lista de fragmentos de documentos procesados por LangChain.
        max_intentos: Número máximo de intentos si falla la creación.
    Returns:
        Instancia de Chroma con los documentos indexados.
    Raises:
        Exception: Si no se pudo crear la base vectorial tras todos los intentos.
    """
    ultimo_error: Exception | None = None

    for intento in range(1, max_intentos + 1):
        try:
            print(f"Creando ChromaDB, intento {intento}/{max_intentos}...")

            vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=embeddings,
                collection_name="rag_rtf_documents"
            )

            print("ChromaDB creada correctamente en memoria.")
            return vectorstore

        except Exception as e:
            ultimo_error = e
            print(f"Error creando ChromaDB o embeddings: {e}")

            if intento < max_intentos:
                espera = 10 * intento
                print(f"Reintentando en {espera} segundos...")
                time.sleep(espera)

        finally:
            print(f"Intento {intento} finalizado.")

    if ultimo_error:
        raise ultimo_error

    raise RuntimeError("No se pudo crear ChromaDB por una causa desconocida.")

vectorstore = crear_vectorstore_con_reintentos(chunks)

retriever = vectorstore.as_retriever(
    search_kwargs={"k": TOP_K}
)

print("Retriever creado correctamente.")


# =========================
# Crear modelo Gemini y prompt RAG
# =========================
llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    temperature=0.2
)

prompt = ChatPromptTemplate.from_template("""
Eres un asistente RAG experto especializado en revenue management para Airbnb.
Responde únicamente con base en el contexto proporcionado.
Reglas obligatorias:
1. Si la respuesta está en el contexto, responde de forma clara y precisa.
2. Si no encuentras la respuesta en el contexto, di: "No encontré esa información en los documentos cargados."
3. Siempre incluye una sección final llamada "Fuentes".
4. En "Fuentes", menciona obligatoriamente el nombre del documento o documentos usados.
5. No inventes fuentes.
6. Responde de forma resumida, usando máximo 5 puntos principales.
7. No repitas información similar entre fuentes.
Contexto:
{context}
Pregunta:
{question}
Respuesta:
""")

chain = prompt | llm | StrOutputParser()


# =========================
# Funciones del chat
# =========================
def format_docs(retrieved_docs: list[Document]) -> str:
    """Formatea documentos recuperados como contexto para el modelo.
    Args:
        retrieved_docs: Lista de documentos recuperados por el retriever.
    Returns:
        Cadena de texto con el contenido de los documentos y sus fuentes.
    """
    formatted: list[str] = []

    for i, doc in enumerate(retrieved_docs, start=1):
        source = doc.metadata.get("source", "Fuente desconocida")
        content = doc.page_content
        formatted.append(f"[Documento {i}: {source}]\n{content}")

    return "\n\n".join(formatted)

def get_sources(retrieved_docs: list[Document]) -> list[str]:
    """Obtiene una lista única de fuentes usadas en la recuperación.
    Args:
        retrieved_docs: Lista de documentos recuperados por similitud.
    Returns:
        Lista de nombres únicos de documentos fuente.
    """
    sources: list[str] = []

    for doc in retrieved_docs:
        source = doc.metadata.get("source", "Fuente desconocida")
        if source not in sources:
            sources.append(source)

    return sources

def rag_chat(
    message: str,
    history: list[dict[str, Any]] | list[tuple[str, str]]
) -> str:
    """Responde una pregunta usando recuperación aumentada por generación.
    Args:
        message: Pregunta enviada por el usuario desde la interfaz.
        history: Historial de conversación recibido desde Gradio.
    Returns:
        Respuesta generada por Gemini con una sección final de fuentes.
    """
    try:
        print(f"Pregunta recibida: {message}")

        retrieved_docs = retriever.invoke(message)

        if not retrieved_docs:
            return "No encontré información relevante en los documentos cargados.\n\nFuentes:\n- Ninguna"

        context = format_docs(retrieved_docs)
        sources = get_sources(retrieved_docs)

        response = chain.invoke({
            "context": context,
            "question": message
        })

        if "Fuentes" not in response:
            response += "\n\nFuentes:\n" + "\n".join(f"- {source}" for source in sources)

        return response

    except Exception as e:
        print("ERROR EN rag_chat:")
        traceback.print_exc()

        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            return (
                "Se alcanzó temporalmente el límite gratuito de la API de Gemini. "
                "Intenta nuevamente en unos minutos."
            )

        return (
            "Ocurrió un error temporal al procesar la pregunta. "
            "Intenta de nuevo en unos segundos."
        )

    finally:
        print("Consulta finalizada.")

# =========================
# Interfaz Gradio
# =========================
custom_css = """
textarea {
    background: #FFFFFF !important;
    color: #222222 !important;
    border: 1px solid #DDDDDD !important;
}
"""

example_questions = [
    "Según los documentos, ¿cómo debo ajustar mis precios en temporada alta para mejorar la ocupación y mantener buenos ingresos?",
    "¿Qué estándares de limpieza debe seguir un anfitrión para mejorar la experiencia del huésped?",
    "¿Cuáles son los errores más comunes en un anuncio de Airbnb y cómo puedo evitarlos?",
    "¿Qué estrategia de descuentos puedo usar para conseguir más reservas sin afectar demasiado mis ingresos?"
]

chat_interface = gr.ChatInterface(
    fn=rag_chat,
    title="Airbnb Strategic Consultant",
    description="Analista de Revenue Management con soporte RAG.",
    chatbot=gr.Chatbot(height=650),
    textbox=gr.Textbox(
        placeholder="Escribe aquí tu pregunta sobre precios, limpieza, anuncios o reseñas...",
        container=True,
        lines=1
    ),
    examples=example_questions,
    cache_examples=False,
)

with gr.Blocks(css=custom_css) as demo:
    chat_interface.render()

    volver_btn = gr.Button("Ver preguntas de ejemplo")

    volver_btn.click(
        fn=lambda: [],
        inputs=None,
        outputs=chat_interface.chatbot,
        queue=False
    )

demo.launch()
