"""Comprueba que el entorno está listo para la corrida final del Gate 2. Nunca imprime la clave.

Uso, desde la raíz del repositorio y con el entorno activo:
    python3 verificar_entorno.py          (o python3 main.py verificar)

Termina con código 1 y una línea "Pendiente: ..." si falta algo; con 0 si está todo.
"""
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "src"))

PAQUETES = ["langchain-core", "langchain-chroma", "chromadb", "langchain-google-genai", "langgraph",
            "langgraph-checkpoint-sqlite", "python-dotenv", "pytest"]
CARPETA_INDICE = RAIZ / "vectorstore"
VERSION_MINIMA = (3, 12)  # numpy 2.5 (dependencia de chromadb en requirements.txt) exige 3.12


def main() -> int:
    problemas, avisos = [], []
    print("Python:", sys.version.split()[0])
    if sys.version_info < VERSION_MINIMA:
        problemas.append(f"usar Python {'.'.join(map(str, VERSION_MINIMA))} o superior")
    if sys.prefix == sys.base_prefix:
        avisos.append("no hay un entorno virtual activo (source venv/bin/activate)")

    for paquete in PAQUETES:
        try:
            print(f"{paquete}: {version(paquete)}")
        except PackageNotFoundError:
            print(f"{paquete}: NO instalado")
            problemas.append(f"instalar {paquete} (pip install -r requirements.txt)")

    try:
        from dotenv import load_dotenv

        from configuracion import NOMBRES_CLAVE, clave_api
        load_dotenv(RAIZ / ".env")
        nombre = next((n for n in NOMBRES_CLAVE if __import__("os").getenv(n)), None)
        print(f"clave de Gemini: {'definida (' + nombre + ')' if clave_api() else 'FALTA'}")
        if not clave_api():
            problemas.append("definir GEMINI_API_KEY (o API_KEY) en el archivo .env "
                             "(sin clave: python3 servicio_rag.py --simulado)")
    except ImportError:
        pass  # ya quedó anotado arriba qué paquete falta

    ignorado = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=RAIZ).returncode == 0
    print(f".env ignorado por git: {'sí' if ignorado else 'NO'}")
    if not ignorado:
        problemas.append('agregar ".env" a .gitignore antes de entregar')

    chunks = 0
    if CARPETA_INDICE.is_dir() and any(CARPETA_INDICE.iterdir()):
        try:
            import chromadb
            cliente = chromadb.PersistentClient(path=str(CARPETA_INDICE))
            chunks = cliente.get_collection("campana_k7").count()
        except Exception:
            chunks = 0
    print(f"índice en {CARPETA_INDICE.name}/: {f'{chunks} chunks' if chunks else 'NO existe o está vacío'}")
    if not chunks:
        avisos.append("el índice no existe todavía: python3 main.py indexar (o el servicio lo crea en su primera "
                      "corrida, unos segundos y 15 embeddings)")

    print()
    for aviso in avisos:
        print("Aviso:", aviso)
    if problemas:
        print("Pendiente: " + "; ".join(problemas))
        return 1
    print("Entorno listo para la corrida final")
    return 0


if __name__ == "__main__":
    sys.exit(main())
