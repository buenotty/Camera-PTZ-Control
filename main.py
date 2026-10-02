import sys
import os

# Adiciona o diretório raiz ao path do Python para importações absolutas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import PTZControlApp

def main() -> None:
    """Ponto de entrada do aplicativo PTZ Control."""
    app = PTZControlApp()
    sys.exit(app.run())

if __name__ == '__main__':
    main()
