"""Run the local desktop application without creating a server or persistent log."""
import sys
from PySide6.QtWidgets import QApplication
from .gui import MainWindow


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('Anonimizador local')
    window=MainWindow();window.show()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
