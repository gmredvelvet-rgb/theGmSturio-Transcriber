"""Punto de entrada principal de Whisperer.

Uso:
    python main.py          → Abre la interfaz gráfica
    python main.py --cli    → Usa la interfaz de línea de comandos
"""

import sys


def main() -> None:
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from transcriber.cli import main as cli_main
        cli_main()
    else:
        from transcriber.gui import launch_gui
        launch_gui()


if __name__ == "__main__":
    main()
