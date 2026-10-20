import sys
import argparse
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from .gui import MainWindow,ASSETS


def main(argv=None):
    parser=argparse.ArgumentParser(description='Solide variant review')
    parser.add_argument('--session',help='Open an existing local Solide session')
    options=parser.parse_args(sys.argv[1:] if argv is None else argv)
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Solide.VariantReview')
    app=QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('Solide');app.setOrganizationName('Solide')
    app.setWindowIcon(QIcon(str(ASSETS/'solide.ico')))
    window=MainWindow();window.show()
    if options.session:
        try:window.load_session_path(options.session)
        except Exception as exc:window.notify_error(str(exc))
    return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
