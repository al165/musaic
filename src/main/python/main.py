import multiprocessing

from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from gui.elements import InstrumentPanel, TrackPanel, TimeView, SectionView
from app import Engine


APP_NAME = "musAIc v1.0.1"

INS_PANEL_HEIGHT = 100
TIMELINE_HEIGHT = 20


class ClientOptions(QtWidgets.QDialog):

    def __init__(self, engine, *args, **kwargs):
        super().__init__(*args, **kwargs)

        print('[ClientOptions]', 'init')

        self._engine = engine

        self.setWindowTitle('musAIc options...')

        layout = QtWidgets.QVBoxLayout()

        self._osc_box = QtWidgets.QGroupBox('OSC')
        osc_layout = QtWidgets.QFormLayout()
        self._osc_box.setLayout(osc_layout)
        self._osc_box.setCheckable(True)
        self._osc_box.setChecked(self._engine.oscOptions['send'])

        self._addr = QtWidgets.QLineEdit(str(self._engine.oscOptions['addr']))
        self._addr.setInputMask('000.000.000.000')
        self._port = QtWidgets.QSpinBox()# str(self._engine.clientOptions['port']))
        self._port.setRange(1024, 65535)
        self._port.setValue(self._engine.oscOptions['port'])
        self._osc_clock = QtWidgets.QCheckBox()
        self._osc_clock.setChecked(self._engine.oscOptions['clock'])

        osc_layout.addRow('Address:', self._addr)
        osc_layout.addRow('Port:', self._port)
        osc_layout.addRow('Send clock:', self._osc_clock)

        layout.addWidget(self._osc_box)

        self._midi_box = QtWidgets.QGroupBox('MIDI')
        midi_layout = QtWidgets.QFormLayout()
        self._midi_box.setLayout(midi_layout)
        self._midi_box.setCheckable(True)
        self._midi_box.setChecked(self._engine.midiOptions['send'])

        self._midi_port = QtWidgets.QComboBox()
        port_names = self._engine.getMidiPorts()
        if port_names:
            self._midi_port.addItems(port_names)
        else:
            self._midi_port.addItem('No MIDI devices found...')

        self._midi_clock = QtWidgets.QCheckBox()
        self._midi_clock.setChecked(self._engine.midiOptions['clock'])

        midi_layout.addRow("MIDI Port:", self._midi_port)
        midi_layout.addRow("Send clock:", self._midi_clock)

        layout.addWidget(self._midi_box)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.setLayout(layout)

    def accept(self):
        self._engine.setOscOut(self._osc_box.isChecked())
        if self._osc_box.isChecked():
            self._engine.setClientOptions(self._addr.text(), int(self._port.value()),
                                          self._osc_clock.isChecked())

        self._engine.setMidiOut(self._midi_box.isChecked())
        if self._midi_box.isChecked():
            port_name = self._midi_port.currentText()
            if port_name == 'No MIDI devices found...':
                port_name = None
            self._engine.setMidiPort(port_name, self._midi_clock.isChecked())

        super().accept()
        return


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, ctx, *args, argv=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self._ctx = ctx

        self.setWindowTitle(APP_NAME)

        resources_path = self._ctx.get_resource()
        print(resources_path)

        self.engine = Engine(resources_path=resources_path, argv=argv)
        self.engine.start()

        self.engine.addCallback('instrument_added', self.instrumentAdded)

        main = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()

        # Main Controls --------------------------------------------------
        controls_layout = QtWidgets.QHBoxLayout()

        load = QtWidgets.QPushButton('open')
        load.clicked.connect(self.load)
        load.setToolTip('Open an existing musAIc project')
        controls_layout.addWidget(load)

        save = QtWidgets.QPushButton('save')
        save.clicked.connect(self.save)
        save.setToolTip('Save musAIc project')
        controls_layout.addWidget(save)

        play = QtWidgets.QPushButton('play')
        play.clicked.connect(self.engine.startPlaying)
        controls_layout.addWidget(play)

        loop = QtWidgets.QPushButton()
        loop.setText(' loop ')
        loop.setCheckable(True)
        loop.clicked[bool].connect(self.engine.setLoopPlayback)
        sp = QtWidgets.QSizePolicy()
        sp.setHorizontalStretch(1)
        loop.setSizePolicy(sp)
        controls_layout.addWidget(loop)

        stop = QtWidgets.QPushButton('stop')
        stop.clicked.connect(self.engine.stopPlaying)
        controls_layout.addWidget(stop)

        send_options = QtWidgets.QPushButton('options')
        send_options.clicked.connect(self.showOptions)
        controls_layout.addWidget(send_options)

        import_ = QtWidgets.QPushButton('import midi')
        import_.clicked.connect(self.importMidi)
        import_.setToolTip('Import a MIDI file into project')
        controls_layout.addWidget(import_)

        export = QtWidgets.QPushButton('export midi')
        export.clicked.connect(self.exportMidi)
        export.setToolTip('Export a MIDI file')
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

        timeline_view = TimeView(self.engine, horizontal_scroll)
        timeline_view.setFixedHeight(TIMELINE_HEIGHT)
        timeline_view.setHorizontalScrollBar(horizontal_scroll)
        timeline_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        timeline_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._instrument_layout.addWidget(timeline_view, 1, 1)

        self._instrument_panels = []
        self._track_view = TrackPanel(self.engine, section_view, timeline_view,
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
        global_controls_layout = QtWidgets.QHBoxLayout()
        bpm = QtWidgets.QSpinBox()
        bpm.setFixedWidth(50)
        bpm.setRange(20, 300)
        bpm.valueChanged.connect(self.engine.setBPM)
        bpm.setValue(80)
        bpm.setToolTip('Beats per minute')
        global_controls_layout.addWidget(bpm)

        transpose = QtWidgets.QSpinBox()
        transpose.setFixedWidth(50)
        transpose.setRange(-12, 12)
        transpose.valueChanged.connect(self.engine.setGlobalTranspose)
        transpose.setValue(0)
        transpose.setToolTip('Global transpose (in semi-tones)')
        global_controls_layout.addWidget(transpose)

        self.global_controls = {
            'bpm': bpm,
            'transpose': transpose
        }

        self._instrument_layout.addLayout(global_controls_layout, 0, 0)

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

    def addInstrument(self, *args):
        instrument = self.engine.addInstrument()

    def instrumentAdded(self, instrument):
        print('[MainWindow]', 'instrumentAdded', instrument.id_)
        panel = InstrumentPanel(instrument, self.engine, self._track_view)
        panel.setFixedHeight(INS_PANEL_HEIGHT)

        self._instrument_scroll_layout.takeAt(len(self._instrument_panels))
        self._instrument_scroll_layout.addWidget(panel, alignment=Qt.AlignLeft)
        self._instrument_scroll_layout.addStretch(1)
        self._instrument_panels.append(panel)
        self._track_view.addInstrument(instrument)
        self._track_view.buildSections(instrument.id_)


    def deleteInstrument(self, instrumentID):
        raise NotImplementedError

    def setBar(self, e):
        print('[MainWindow]', 'setBar', e)

    def keyPressEvent(self, event):
        print('[MainWindow]', 'keyPressEvent', event)
        if type(event) == QtGui.QKeyEvent:
            if event.key() == QtCore.Qt.Key_Space:
                self.engine.togglePlay()

    def updateCursor(self):
        try:
            bar_num, tick = self.engine.getTime()
            self._track_view.updateCursor(bar_num, tick)
        finally:
            QtCore.QTimer.singleShot(1000/20, self.updateCursor)

    def load(self):
        print('[MainWindow]', 'Loading...')
        file_name = QtWidgets.QFileDialog.getOpenFileName(self, 'Open project...',
                                                          filter='musAIc (*.mus)')
        print(file_name)

        # first delete everything...
        self._track_view.reset()
        self._track_view.update()

        while self._instrument_scroll_layout.count():
            widget = self._instrument_scroll_layout.takeAt(0)
            if widget and widget.widget():
                widget.widget().setParent(None)

        self._instrument_scroll_layout.addStretch(1)
        self._instrument_panels = []

        # load_file...
        self.engine.loadFile(file_name[0])

        # rebuild GUI...
        #for instrument in self.engine.instruments.values():
        #    print(instrument.id_, instrument.sections, instrument.chan)
        #    panel = InstrumentPanel(instrument, self.engine, self._track_view)
        #    panel.setFixedHeight(INS_PANEL_HEIGHT)

        #    panel.setToolTip(f'{instrument.name}, {instrument.id_}, {instrument.chan}')
        #    self._instrument_scroll_layout.takeAt(len(self._instrument_panels))
        #    self._instrument_scroll_layout.addWidget(panel, alignment=Qt.AlignLeft)
        #    self._instrument_scroll_layout.addStretch(1)
        #    self._instrument_panels.append(panel)
        #    self._track_view.addInstrument(instrument)
        #    self._track_view.buildSections(instrument.id_)

        self.global_controls['bpm'].setValue(self.engine.bpm)
        self.global_controls['transpose'].setValue(self.engine.global_transpose)

        self._track_view.update()

        print('[MainWindow]', 'finished resetting GUI')

    def save(self):
        print('[MainWindow]', 'Saving...')
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Save project...', filter='musAIc (*.mus)')
        print(file_name)
        self.engine.saveFile(file_name[0])

    def importMidi(self):
        print('[MainWindow]', 'Importing...')
        file_name = QtWidgets.QFileDialog.getOpenFileName(self, 'Import MIDI...', filter='MIDI (*.mid *.midi)')
        print(file_name)
        self.engine.importMidiFile(file_name[0])

    def exportMidi(self):
        print('[MainWindow]', 'Exporting...')
        file_name = QtWidgets.QFileDialog.getSaveFileName(self, 'Export MIDI...', filter='MIDI (*.mid *.midi)')
        print(file_name)
        self.engine.exportMidiFile(file_name[0])


if __name__ == '__main__':
    multiprocessing.freeze_support()

    import sys

    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext

    style = appctxt.get_resource('darkStyle.stylesheet')
    appctxt.app.setStyleSheet(open(style).read())

    window = MainWindow(ctx=appctxt, argv=sys.argv)
    window.setMinimumHeight(500)
    window.setGeometry(20, 40, 1200, 600)
    window.show()

    exit_code = appctxt.app.exec_()      # 2. Invoke appctxt.app.exec_()

    window.close()

    sys.exit(exit_code)
