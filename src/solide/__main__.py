import sys
from PyQt6.QtWidgets import QApplication
from .gui import MainWindow


def main():
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Solide');app.setOrganizationName('Solide')
    window=MainWindow();window.show()
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
