from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from gui.elements import InstrumentPanel, TrackView, TimeView, SectionView
from app import Player, Engine

INS_PANEL_HEIGHT = 100
TIMELINE_HEIGHT = 20

class ClientOptions(QtWidgets.QDialog):

    def __init__(self, engine, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print('[ClientOptions]', 'init')

        self._engine = engine

        self.setWindowTitle('musAIc options...')

        layout = QtWidgets.QVBoxLayout()
        form_layout = QtWidgets.QFormLayout()
        layout.addLayout(form_layout)

        self._addr = QtWidgets.QLineEdit(str(self._engine.clientOptions['addr']))
        self._addr.setInputMask('000.000.000.000')
        self._port = QtWidgets.QSpinBox()# str(self._engine.clientOptions['port']))
        self._port.setRange(1024, 65535)
        self._port.setValue(self._engine.clientOptions['port'])
        self._clock = QtWidgets.QCheckBox()
        self._clock.setChecked(self._engine.clientOptions['clock'])

        form_layout.addRow('Address:', self._addr)
        form_layout.addRow('Port:', self._port)
        form_layout.addRow('Send clock:', self._clock)


        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.setLayout(layout)

    def accept(self):
        self._engine.setClientOptions(self._addr.text(), int(self._port.value()), self._clock.isChecked())
        super().accept()
        return


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, ctx, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self._ctx = ctx

        self.setWindowTitle("musAIc v1.0_dev (qt5)")

        resources_path = self._ctx.get_resource()
        print(resources_path)

        self.engine = Engine(resources_path=resources_path)
        self.engine.start()

        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # Main Controls --------------------------------------------------
        controls_layout = QtWidgets.QHBoxLayout()
        play = QtWidgets.QPushButton('play')
        play.clicked.connect(self.engine.startPlaying)
        controls_layout.addWidget(play)

        stop = QtWidgets.QPushButton('stop')
        stop.clicked.connect(self.engine.stopPlaying)
        controls_layout.addWidget(stop)

        send_options = QtWidgets.QPushButton('options')
        send_options.clicked.connect(self.showOptions)
        controls_layout.addWidget(send_options)

        export = QtWidgets.QPushButton('export')
        export.clicked.connect(self.exportMidi)
        controls_layout.addWidget(export)

        main_layout.addLayout(controls_layout)

        # Section View ---------------------------------------------------
        section_view = SectionView(self.engine)
        section_view.setMinimumHeight(110)

        # Instrument Layout ----------------------------------------------

        self._instrument_layout = QtWidgets.QGridLayout()
        self._instrument_layout.setSpacing(0)
        self._instrument_layout.setContentsMargins(0, 0, 0, 0)

        horizontal_scroll = QtWidgets.QScrollBar(Qt.Horizontal)
        self._instrument_layout.addWidget(horizontal_scroll, 0, 1)

        vertical_scroll = QtWidgets.QScrollBar(Qt.Vertical)
        self._instrument_layout.addWidget(vertical_scroll, 2, 2)

        instrument_scroll_panel = QtWidgets.QScrollArea()
        instrument_scroll_panel.setVerticalScrollBar(vertical_scroll)
        instrument_scroll_panel.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        instrument_scroll_panel.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        instrument_scroll_panel.setWidgetResizable(True)
        instrument_scroll_panel.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        instrument_panel_widget = QtWidgets.QWidget()
        self._instrument_scroll_layout = QtWidgets.QVBoxLayout()
        self._instrument_scroll_layout.setSpacing(0)
        self._instrument_scroll_layout.setContentsMargins(0, 0, 0, 0)
        #self._instrument_scroll_layout
        instrument_panel_widget.setLayout(self._instrument_scroll_layout)
        instrument_scroll_panel.setWidget(instrument_panel_widget)

        self._instrument_layout.addWidget(instrument_scroll_panel, 2, 0)

        timeline_view = TimeView(self.engine)
        timeline_view.setFixedHeight(TIMELINE_HEIGHT)
        timeline_view.setHorizontalScrollBar(horizontal_scroll)
        timeline_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        timeline_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._instrument_layout.addWidget(timeline_view, 1, 1)

        self._instrument_panels = []
        self._track_view = TrackView(section_view, timeline_view,
                                      instrument_panel_height=INS_PANEL_HEIGHT,
                                      timeline_height=TIMELINE_HEIGHT)
        self._track_view.setMinimumHeight(INS_PANEL_HEIGHT)

        add_instrument_button = QtWidgets.QPushButton('+')
        add_instrument_button.clicked.connect(self.addInstrument)
        add_instrument_button.setFixedHeight(TIMELINE_HEIGHT)
        self._instrument_layout.addWidget(add_instrument_button, 1, 0)
        self._instrument_layout.addWidget(self._track_view, 2, 1)
        self._instrument_layout.setColumnStretch(1, 2)

        self._track_view.setHorizontalScrollBar(horizontal_scroll)
        self._track_view.setVerticalScrollBar(vertical_scroll)
        self._track_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._track_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        section_view.setTrackView(self._track_view)

        # global controls...
        global_controls = QtWidgets.QHBoxLayout()
        bpm = QtWidgets.QSpinBox()
        bpm.setFixedWidth(50)
        bpm.setRange(20, 300)
        bpm.valueChanged.connect(self.engine.setBPM)
        bpm.setValue(80)
        bpm.setToolTip('Beats per minute')
        global_controls.addWidget(bpm)

        transpose = QtWidgets.QSpinBox()
        transpose.setFixedWidth(50)
        transpose.setRange(-12, 12)
        transpose.valueChanged.connect(self.engine.setGlobalTranspose)
        transpose.setValue(0)
        transpose.setToolTip('Global transpose (in semi-tones)')
        global_controls.addWidget(transpose)

        self._instrument_layout.addLayout(global_controls, 0, 0)

        main_layout.addLayout(self._instrument_layout)
        main_layout.setStretch(1, 2)

        main_layout.addWidget(section_view)

        # ----------------------------------------------------------------

        main.setLayout(main_layout)
        self.setCentralWidget(main)

        self.updateCursor()

        self.addInstrument()

    def close(self):
        print('[MainWindow]', 'Closing...')
        self.engine.join(timeout=1)

    def showOptions(self):
        print('[MainWindow]', 'showOptions')
        dialog = ClientOptions(self.engine)
        dialog.exec_()

    def addInstrument(self):
        instrument = self.engine.addInstrument()
        panel = InstrumentPanel(instrument, self.engine, self._track_view)
        print('[MainWindow]', panel.sizeHint())
        panel.setFixedHeight(INS_PANEL_HEIGHT)

        self._instrument_scroll_layout.takeAt(len(self._instrument_panels))
        self._instrument_scroll_layout.addWidget(panel, alignment=Qt.AlignLeft)
        self._instrument_scroll_layout.addStretch(1)
        self._instrument_panels.append(panel)
        self._track_view.addInstrument(instrument)

        panel.newSection()

    def deleteInstrument(self, instrumentID):
        pass

    def setBar(self, e):
        print('[MainWindow]', 'setBar', e)

    def updateCursor(self):
        try:
            #print('[MainWindow]', 'updateCursor', self.engine.getTime())
            bar_num, tick = self.engine.getTime()
            self._track_view.updateCursor(bar_num, tick)
        finally:
            QtCore.QTimer.singleShot(1000/20, self.updateCursor)

    def exportMidi(self):
        print('[MainWindow]', 'Exporting...')
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Export MIDI...')
        print(file_name)
        self.engine.exportMidiFile(file_name[0])



if __name__ == '__main__':
    import sys

    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext

    style = appctxt.get_resource('darkStyle.stylesheet')
    appctxt.app.setStyleSheet(open(style).read())

    window = MainWindow(ctx=appctxt)
    window.setMinimumHeight(500)
    window.setGeometry(20, 40, 1200, 600)
    window.show()

    exit_code = appctxt.app.exec_()      # 2. Invoke appctxt.app.exec_()

    window.close()

    sys.exit(exit_code)
