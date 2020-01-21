from copy import deepcopy
from random import randint
from collections import defaultdict

from colorsys import hsv_to_rgb

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt

from core import DEFAULT_META_DATA, DEFAULT_SECTION_PARAMS, DEFAULT_AI_PARAMS
from gui.sliders import BoxRangeSlider, BoxSlider, Knob


DEFAULT_BAR_WIDTH = 80


class TimeView(QtWidgets.QGraphicsView):

    def __init__(self, engine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._engine = engine

    def mousePressEvent(self, e):
        #print('[TimeView]', 'mousePressEvent', e)
        scene = self.scene()
        if not scene:
            return
        bar_width = scene.parent().getBarWidth()
        bar_num = int(self.mapToScene(e.x(), e.y()).x()//bar_width)
        self._engine.setBarNumber(bar_num)

    def wheelEvent(self, e):
        #print('[TimeView]', e.angleDelta().y())

        if e.angleDelta().y() > 0:
            # zoom out...
            self.scene().parent().zoom(-1)
        else:
            # zoom in...
            self.scene().parent().zoom(1)


class TrackScene(QtWidgets.QGraphicsScene):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def drawBackground(self, painter, rect):
        #print('[TrackScene]', 'drawBackground()')
        scene_rect = self.parent().getSceneRect()

        bar_width = self.parent().getBarWidth()
        instrument_height = self.parent().getInstrumentHeight()

        brush = QtGui.QBrush()
        brush.setStyle(Qt.SolidPattern)
        brush.setColor(QtGui.QColor('#151515'))
        painter.fillRect(rect, brush)

        line_pen = QtGui.QPen(QtGui.QColor('#333333'), 1, Qt.SolidLine)
        painter.setPen(line_pen)

        width = max(painter.device().width(), scene_rect.width())
        height = scene_rect.height()
        num_bars = width//bar_width + 1
        num_ins = height//instrument_height + 1

        # draw vertical lines...
        if bar_width <= 10:
            skip = 8
        elif bar_width <= 20:
            skip = 4
        elif bar_width <= 40:
            skip = 2
        else:
            skip = 1

        lines = []
        for i in range(0, int(num_bars), skip):
            x = i*bar_width
            if x >= rect.left() and x <= rect.right():
                lines.append(QtCore.QLineF(x, rect.top(), x, rect.bottom()))
                #painter.drawLine(x, rect.top(), x, rect.bottom())
            painter.drawText(i*bar_width + 5, -10, str(i+1))

        painter.drawLines(lines)

        # draw horizontal lines...
        line_pen.setWidth(3)
        painter.setPen(line_pen)

        for j in range(int(num_ins)):
            y = j*instrument_height
            if y > rect.top() and y <= rect.bottom():
                painter.drawLine(rect.left(), y, rect.right(), y)

        super().drawBackground(painter, rect)

class TrackView(QtWidgets.QWidget):
    def __init__(self, section_view, timeline_view, *args,
                 instrument_panel_height=120, timeline_height=20, **kwargs):

        super().__init__(*args, **kwargs)

        self._section_view = section_view
        self._timeline_view = timeline_view
        self._instrument_panel_height = instrument_panel_height
        self._timeline_height = timeline_height

        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self._bar_width = DEFAULT_BAR_WIDTH
        self._track_scene = TrackScene(0.0, 0.0, 1000.0, 1000.0, self)
        self._track_scene.selectionChanged.connect(self.newSelection)

        self._track_view = QtWidgets.QGraphicsView(self._track_scene)
        self._track_view.setCacheMode(QtWidgets.QGraphicsView.CacheBackground)
        self._track_view.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._track_view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)
        self._track_view.setMinimumWidth(1000)
        layout.addWidget(self._track_view)

        self._timeline_view.setScene(self._track_scene)
        timeline_rect = QtCore.QRectF(0, -timeline_height, 1000, timeline_height-2)
        self._timeline_view.setSceneRect(timeline_rect)
        self._timeline_view.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._timeline_view.setViewportUpdateMode(QtWidgets.QGraphicsView.SmartViewportUpdate)

        cursor = QtCore.QLineF(0.0, -self._timeline_height, 0.0, self._instrument_panel_height)
        cursor_pen = QtGui.QPen(QtGui.QColor('orange'))
        self._track_cursor = self._track_scene.addLine(cursor, cursor_pen)
        self._track_cursor.setZValue(10)

        self.setLayout(layout)

        self._instruments = dict()
        self._section_boxes = defaultdict(dict)

        self.setEnabled(True)

    def addInstrument(self, instrument):
        self._instruments[instrument.id_] = instrument
        self._section_boxes[instrument.id_] = dict()
        self._track_scene.update()

    def rebuildTrack(self, instrumentID):
        track = dict()
        for sb in self._section_boxes[instrumentID].values():
            bar_num = sb.bar_num
            block = sb.block

            while bar_num in track:
                bar_num += 1

            track[bar_num] = block

        self._instruments[instrumentID].track.setTrack(track)

    def buildSections(self, instrumentID):
        #print('[TrackView]', 'buildSections', instrumentID)

        instrument = self._instruments[instrumentID]
        track = instrument.track

        y = self._instrument_panel_height * instrumentID

        for start_time, block in track.getBlocks():
            try:
                sb = self._section_boxes[instrumentID][block.id_]
            except KeyError:
                #print('[TrackView]', 'new section box')
                sb = SectionBox(block, instrument, self, start_time, height=self._instrument_panel_height)
                self._track_scene.addItem(sb)
                self._section_boxes[instrumentID][block.id_] = sb

                self._track_scene.clearSelection()
                sb.setSelected(True)
                self.newSelection()

            sb.bar_num = start_time
            x = self._bar_width * start_time
            sb.setPos(x, y)

        self.updateRects()

    def newSelection(self, *args):
        #print('[TrackView]', 'newSelection')
        selection = self._track_scene.selectedItems()
        if selection:
            selection = selection[0]
            self._section_view.setSection(selection)
        else:
            self._section_view.setSection(None)

    def deleteSectionBox(self, instrumentID, blockID):
        sb = self._section_boxes[instrumentID][blockID]
        self._track_scene.removeItem(sb)
        del self._section_boxes[instrumentID][blockID]

    def updateCursor(self, bar_num, tick):
        #print('[TrackView]', 'updateCursor', bar_num, tick)
        x = (bar_num + tick/96) * self._bar_width
        self._track_cursor.setPos(int(x), -self._timeline_height)
        self._track_view.update()

    def updateRects(self):
        scene_rect = self.getSceneRect()
        self._track_scene.setSceneRect(scene_rect)

        time_scene_rect = self._timeline_view.sceneRect()
        time_scene_rect.setWidth(scene_rect.width())
        self._timeline_view.setSceneRect(time_scene_rect)

    def getSceneRect(self):
        x = 0
        for ins in self._instruments.values():
            x = max(x, len(ins.track))
        x *= self._bar_width
        y = len(self._instruments.values()) * self._instrument_panel_height
        self._track_cursor.setLine(0.0, -self._timeline_height, 0.0, y+self._timeline_height)
        return QtCore.QRectF(0, 0, x, y)

    def getBarWidth(self):
        return self._bar_width

    def setBarWidth(self, bar_width):
        if bar_width < 5:
            bar_width = 5
        elif bar_width > 100:
            bar_width = 100
        self._bar_width = bar_width

        for id_, section_boxes in self._section_boxes.items():
            for section_box in section_boxes.values():
                section_box.setBarWidth(bar_width)
                x = section_box.bar_num * self._bar_width
                y = self._instrument_panel_height * id_
                section_box.setPos(x, y)
            #self.buildSections(id_)

        self.updateRects()
        self._track_scene.update()
        self._track_view.update()

    def zoom(self, factor):
        if factor > 0:
            self.setBarWidth(self._bar_width+2)
        elif factor < 0:
            self.setBarWidth(self._bar_width-2)

    def getInstrumentHeight(self):
        return self._instrument_panel_height

    def getTimelineHeight(self):
        return self._timeline_height

    def getTrackScene(self):
        return self._track_scene

    def reset(self):
        for section_boxes in self._section_boxes.values():
            for sb in section_boxes.values():
                sb.unhookSection()
                self._track_scene.removeItem(sb)

        self._instruments = dict()
        self._section_boxes = defaultdict(dict)
        self._bar_width = DEFAULT_BAR_WIDTH

    def __getattr__(self, name):
        if name in self.__dict__:
            return self[name]

        try:
            return getattr(self._track_view, name)
        except AttributeError:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                self.__class__.__name__, name
            ))


class SectionBox(QtWidgets.QGraphicsItem):
    ''' A canvas of drawn notes '''
    def __init__(self, block, instrument, track_view, bar_num, height=80, *args, **kwargs):
        super(QtWidgets.QGraphicsItem, self).__init__(*args, **kwargs)

        self.block = block
        self.section = block.sections[0]
        self.section.addCallback(self.sectionChanged)

        self.instrument = instrument
        self._track_view = track_view
        self.bar_num = bar_num
        self._height = height

        self._bar_width = self._track_view.getBarWidth()
        self._y = self.instrument.id_ * self._track_view.getInstrumentHeight()

        if self.section.type_ == 'fixed':
            r = g = b = 0.3
        else:
            hue = (self.section.id_ * 0.16) % 1.0
            r, g, b = hsv_to_rgb(hue, 0.8, 0.5)
        hex_color = f'#{hex(int(r*255))[2:]}{hex(int(g*255))[2:]}{hex(int(b*255))[2:]}'
        self._section_color = QtGui.QColor(hex_color)

        self._rect = QtCore.QRectF(0, 0, len(self.section)*self._bar_width, height)
        self._backgroud_color = QtGui.QColor('#222222')
        self._repeat_background_color = QtGui.QColor('#101010')
        self._main_note_color = QtGui.QColor('#aaaaaa')
        self._second_note_color = QtGui.QColor('#666666')

        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges, True)

        self._dragged = False

    def unhookSection(self):
        self.section.removeCallback(self.sectionChanged)

    def sectionChanged(self):
        self.update(self._rect)

    def paint(self, painter, *args, **kwargs):
        self._rect = QtCore.QRectF(0, 0, len(self.section)*self._bar_width, self._height)

        #self._bar_width = self._track_view.getBarWidth()
        brush = QtGui.QBrush()
        pen = QtGui.QPen()

        width = self._bar_width * len(self.section)
        height = self._height - 1

        # draw section box...
        brush.setColor(self._section_color)
        brush.setStyle(Qt.SolidPattern)
        painter.setBrush(brush)
        if self.isSelected():
            pen.setColor(QtGui.QColor('white'))
            pen.setWidth(2)
            painter.setPen(pen)
            self.setZValue(5)
        else:
            painter.setPen(Qt.NoPen)
            self.setZValue(1)
        painter.drawRect(0, 0, width, height)

        # draw track...
        brush.setColor(self._backgroud_color)
        brush.setStyle(Qt.SolidPattern)
        painter.setPen(Qt.NoPen)
        painter.fillRect(QtCore.QRect(0, 15, width, height-15), brush)

        pen.setColor(QtGui.QColor("black"))
        pen.setCapStyle(Qt.FlatCap)
        pen.setWidth(1)
        painter.setPen(pen)
        if len(self.section.name)*5 < len(self.section)*self._bar_width :
            painter.drawText(10, 13, self.section.name)

        # draw bar lines...
        for i in range(0, len(self.section)):
            x = i*self._bar_width
            if i%self.section.params['length'] == 0 and self.section.params['loop_num'] > 1:
                painter.drawLine(x, 0, x, height)
            elif self.section.type_ == 'ai' and (i+self.section.params['loop_alt_len']) % self.section.params['length'] == 0 \
                 and self.section.params['loop_num'] > 1:
                painter.drawLine(x, 5, x, height)
                painter.drawLine(x, 5, x+self.section.params['loop_alt_len']*self._bar_width, 5)
            elif self._bar_width > 40:
                pen.setColor(QtGui.QColor('#303030'))
                painter.setPen(pen)
                painter.drawLine(x, 15, x, height)
                pen.setColor(QtGui.QColor("black"))
                painter.setPen(pen)

        # fill in the notes...
        pen.setColor(self._main_note_color)
        pen.setWidth(2)
        painter.setPen(pen)

        lines = []

        for i, measure in enumerate(self.section.flatMeasures):

            if self._bar_width > 10:
                if not measure or (measure.isEmpty() and not measure.genRequestSent):
                    # draw red x...
                    painter.drawText(self._bar_width*i+5, 25, "X")
                    continue

                if measure.genRequestSent:
                    painter.drawText(self._bar_width*i+5, 25, "O")
                    continue

            for j, note in enumerate(measure.getNotes()):
                y = height - note[0] + 20
                x1 = self._bar_width * (i + note[1]/96)
                x2 = self._bar_width * (i + note[2]/96) - 1

                # for small scales, only draw every second note
                if (x2-x1 > 0) and (x2-x1 > 2 or j%2==0):
                    lines.append(QtCore.QLineF(x1, y, x2, y))

        painter.drawLines(lines)

    def setBarWidth(self, bar_width):
        self._bar_width = bar_width

    def boundingRect(self):
        return self._rect

    def mouseMoveEvent(self, e):
        #print('[SectionBox]', 'mouseMoveEvent', e)
        self._dragged = True
        #self._track_view.ensureVisible(self)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        #print('[SectionBox]', 'mouseReleaseEvent', e)
        if self._dragged:
            self._dragged = False
            self.bar_num = int(self.pos().x() // self._bar_width)

            self._track_view.rebuildTrack(self.instrument.id_)
            #self.instrument.track.moveSectionTo(self.section.id_, bar)
        #self._track_view.ensureVisible(self)
        super().mouseReleaseEvent(e)

    def getSectionColor(self):
        return self._section_color

    def itemChange(self, constant, value):
        #print('[SectionBox]', 'itemChange()', constant, value)
        if constant == QtWidgets.QGraphicsItem.ItemPositionChange:
            new_x = round(value.x()/self._bar_width)*self._bar_width
            new_x = max(0, new_x)
            value = QtCore.QPointF(new_x, self._y)
            #vis_rect = QtCore.QRectF(new_x, self._y, self._bar_width+10, 10)
            #self._track_view.ensureVisible(vis_rect)
            return value
        return super().itemChange(constant, value)


class SectionParameters(QtWidgets.QFrame):

    def __init__(self, engine, track_view=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._engine = engine
        self._track_view = track_view

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain)

        self._section_box = None
        self._section = None
        self._instrument = None

        sp = QtWidgets.QSizePolicy()
        sp.setRetainSizeWhenHidden(True)
        sp.setHorizontalStretch(2)
        #sp.setHorizontalPolicy(QtWidgets.QSizePolicy.MinimumExpanding)

        self.parameters = dict()

        parameter_layout = QtWidgets.QGridLayout()
        parameter_layout.setSpacing(4)
        parameter_layout.setContentsMargins(2, 2, 2, 2)

        self._section_name = QtWidgets.QLabel()
        self._section_name.setAutoFillBackground(True)
        parameter_layout.addWidget(self._section_name, 0, 0, 1, 7)
        parameter_layout.setRowStretch(0, 0.5)

        self._boxes = {
            'action': self.actionBox(),
            'playback': self.playbackBox(),
            'structure': self.structureBox(),
            'lead': self.leadBox(),
            'sample': self.sampleBox(),
            'injection': self.injectionBox(),
            'meta': self.metaBox()
        }

        parameter_layout.addWidget(self._boxes['action'], 1, 0, 3, 1)
        parameter_layout.addWidget(self._boxes['playback'], 1, 1, 3, 1)
        parameter_layout.addWidget(self._boxes['structure'], 1, 2, 3, 1)
        parameter_layout.addWidget(self._boxes['lead'], 1, 3, 3, 1)
        parameter_layout.addWidget(self._boxes['sample'], 1, 4, 3, 1)
        parameter_layout.addWidget(self._boxes['injection'], 1, 5, 3, 1)
        parameter_layout.addWidget(self._boxes['meta'], 1, 6, 3, 1)

        self.lead = self.parameters['lead']
        self.length = self.parameters['length']
        self.loop_num = self.parameters['loop_num']
        self.loop_alt_len = self.parameters['loop_alt_len']
        self.loop_alt_num = self.parameters['loop_alt_num']

        for p in self.parameters.values():
            p.setSizePolicy(sp)
            p.setMinimumWidth(60)
            if isinstance(p, QtWidgets.QComboBox):
                p.view().setMinimumWidth(p.minimumSizeHint().width())

        parameter_layout.setColumnStretch(10, 2)
        self.setLayout(parameter_layout)

        self.parameterChanged()

    def actionBox(self):
        action_box = QtWidgets.QGroupBox('Actions')
        action_layout = QtWidgets.QGridLayout()
        action_layout.setSpacing(2)
        action_layout.setContentsMargins(2, 2, 2, 2)
        action_box.setLayout(action_layout)

        duplicate_section = QtWidgets.QPushButton('dup')
        duplicate_section.clicked.connect(self.duplicateSection)
        action_layout.addWidget(duplicate_section, 0, 0)

        delete_section = QtWidgets.QPushButton('del')
        delete_section.clicked.connect(self.deleteSection)
        action_layout.addWidget(delete_section, 0, 1)

        generate = QtWidgets.QPushButton('gen')
        generate.clicked.connect(self.generateMeasures)
        action_layout.addWidget(generate, 1, 0)

        regenerate = QtWidgets.QPushButton('re-gen')
        regenerate.clicked.connect(lambda x: self.generateMeasures(gen_all=True))
        action_layout.addWidget(regenerate, 1, 1)

        return action_box

    def playbackBox(self):

        playback_box = QtWidgets.QGroupBox('Playback')
        playback_layout = QtWidgets.QGridLayout()
        playback_layout.setSpacing(2)
        playback_layout.setContentsMargins(2, 2, 2, 2)
        playback_box.setLayout(playback_layout)

        self.parameters['transpose_octave'] = QtWidgets.QSpinBox()
        self.parameters['transpose_octave'].setRange(-3, 3)
        self.parameters['transpose_octave'].setValue(0)
        self.parameters['transpose_octave'].setToolTip('Transpose by octave')
        self.parameters['transpose_octave'].valueChanged.connect(self.parameterChanged)
        playback_layout.addWidget(self.parameters['transpose_octave'], 0, 0)

        self.parameters['note_length'] = BoxSlider()
        self.parameters['note_length'].setRange(0, 96)
        self.parameters['note_length'].setToolTip('Override the length of each note (0 sets to original lengths)')
        self.parameters['note_length'].setMinimumWidth(100)
        self.parameters['note_length'].setMinimumHeight(15)
        self.parameters['note_length'].valueChanged.connect(self.parameterChanged)
        playback_layout.addWidget(self.parameters['note_length'], 1, 0)

        self.parameters['velocity_range'] = BoxRangeSlider()
        self.parameters['velocity_range'].setRange(0, 127)
        self.parameters['velocity_range'].left = 80
        self.parameters['velocity_range'].right = 100
        self.parameters['velocity_range'].setMinimumWidth(100)
        self.parameters['velocity_range'].setMinimumHeight(15)
        self.parameters['velocity_range'].setToolTip('Sets the range of possible velocity values')
        self.parameters['velocity_range'].rangeChanged.connect(self.parameterChanged)
        playback_layout.addWidget(self.parameters['velocity_range'], 2, 0)

        return playback_box

    def structureBox(self):
        loop_box = QtWidgets.QGroupBox('Structure')
        loop_layout = QtWidgets.QGridLayout()
        loop_layout.setSpacing(2)
        loop_layout.setContentsMargins(2, 2, 2, 2)
        loop_box.setLayout(loop_layout)

        self.parameters['length'] = QtWidgets.QSpinBox()
        self.parameters['length'].setRange(1, 64)
        self.parameters['length'].setValue(4)
        self.parameters['length'].setToolTip("Length of the section")
        self.parameters['length'].valueChanged.connect(self.parameterChanged)
        loop_layout.addWidget(self.parameters['length'], 0, 0)

        self.parameters['loop_num'] = QtWidgets.QSpinBox()
        self.parameters['loop_num'].setRange(1, 32)
        self.parameters['loop_num'].setToolTip("Number of times this section is played")
        self.parameters['loop_num'].valueChanged.connect(self.parameterChanged)
        loop_layout.addWidget(self.parameters['loop_num'], 0, 1)

        self.parameters['loop_alt_len'] = QtWidgets.QSpinBox()
        self.parameters['loop_alt_len'].setRange(0, 4)
        self.parameters['loop_alt_len'].setToolTip("Length of alternate ending")
        self.parameters['loop_alt_len'].valueChanged.connect(self.parameterChanged)
        loop_layout.addWidget(self.parameters['loop_alt_len'], 1, 0)

        self.parameters['loop_alt_num'] = QtWidgets.QSpinBox()
        self.parameters['loop_alt_num'].setRange(2, 8)
        self.parameters['loop_alt_num'].setToolTip("Number of alternate endings")
        self.parameters['loop_alt_num'].valueChanged.connect(self.parameterChanged)
        loop_layout.addWidget(self.parameters['loop_alt_num'], 1, 1)

        return loop_box

    def leadBox(self):
        lead_box = QtWidgets.QGroupBox('Lead')
        lead_layout = QtWidgets.QVBoxLayout()
        lead_layout.setSpacing(2)
        lead_layout.setContentsMargins(2, 2, 2, 2)
        lead_box.setLayout(lead_layout)

        self.parameters['lead'] = QtWidgets.QComboBox()
        self.parameters['lead'].addItem("None")
        self.parameters['lead'].setToolTip("Lead instrument to follow")
        self.parameters['lead'].setFrame(False)
        self.parameters['lead'].currentIndexChanged.connect(self.parameterChanged)
        lead_layout.addWidget(self.parameters['lead'])

        self.parameters['lead_mode'] = QtWidgets.QComboBox()
        self.parameters['lead_mode'].addItems(['both', 'melody'])
        self.parameters['lead_mode'].setVisible(False)
        self.parameters['lead_mode'].setToolTip("Take either 'melody' from lead instrument or 'both' melody and rhythm")
        self.parameters['lead_mode'].currentIndexChanged.connect(self.parameterChanged)
        lead_layout.addWidget(self.parameters['lead_mode'])

        return lead_box

    def sampleBox(self):
        sample_box = QtWidgets.QGroupBox('Sample')
        sample_layout = QtWidgets.QVBoxLayout()
        sample_layout.setSpacing(2)
        sample_layout.setContentsMargins(2, 2, 2, 2)
        sample_box.setLayout(sample_layout)

        self.parameters['sample_mode'] = QtWidgets.QComboBox()
        self.parameters['sample_mode'].addItems(['best', 'top', 'dist'])
        self.parameters['sample_mode'].setToolTip("Either take the most likely ('best'), from the top 5 best ('top'), or draw from the full distribution of possible notes and rhythms ('dist')")
        self.parameters['sample_mode'].setCurrentText('dist')
        self.parameters['sample_mode'].currentIndexChanged.connect(self.parameterChanged)
        sample_layout.addWidget(self.parameters['sample_mode'])

        self.parameters['chord_mode'] = QtWidgets.QComboBox()
        self.parameters['chord_mode'].addItems(['auto', 'force', '1', '2', '3', '4'])
        self.parameters['chord_mode'].setToolTip("Chord mode: let AI 'auto' choose when to make chords, 'force' to make all chords, or a max number of notes to play at once")
        self.parameters['chord_mode'].setCurrentText('auto')
        self.parameters['chord_mode'].currentIndexChanged.connect(self.parameterChanged)

        #self.parameters['chord_mode'] = QtWidgets.QSpinBox()
        #self.parameters['chord_mode'].setRange(0, 4)
        #self.parameters['chord_mode'].setSpecialValueText('auto')
        #self.parameters['chord_mode'].setToolTip('Chord mode')
        #self.parameters['chord_mode'].valueChanged.connect(self.parameterChanged)
        sample_layout.addWidget(self.parameters['chord_mode'])

        return sample_box

    def injectionBox(self):
        injection_box = QtWidgets.QGroupBox('Style')
        injection_layout = QtWidgets.QGridLayout()
        injection_layout.setSpacing(2)
        injection_layout.setContentsMargins(2, 2, 2, 2)
        injection_box.setLayout(injection_layout)

        self.parameters['context_mode'] = QtWidgets.QComboBox()
        self.parameters['context_mode'].addItems(['real', 'inject'])
        self.parameters['context_mode'].setToolTip("Use the 'real' previous measures or 'inject' new measures")
        self.parameters['context_mode'].currentIndexChanged.connect(self.parameterChanged)
        injection_layout.addWidget(self.parameters['context_mode'], 0, 0, 1, 3)

        self.injection_params = {
            'scale': QtWidgets.QComboBox(),
            'qb': QtWidgets.QPushButton(),
            'eb': QtWidgets.QPushButton(),
            'lb': QtWidgets.QPushButton(),
            'fb': QtWidgets.QPushButton(),
            'tb': QtWidgets.QPushButton()
        }

        sp = QtWidgets.QSizePolicy()
        sp.setRetainSizeWhenHidden(True)
        sp.setHorizontalStretch(2)

        self.injection_params['scale'].addItems(['maj', 'min', 'pen', '5th'])
        self.injection_params['scale'].setSizePolicy(sp)
        injection_layout.addWidget(self.injection_params['scale'], 0, 3, 1, 2)

        for i, cb in enumerate(['qb', 'eb', 'lb', 'fb', 'tb']):
            button = self.injection_params[cb]
            button.setSizePolicy(sp)
            button.setText(cb)
            button.setCheckable(True)
            button.clicked[bool].connect(self.parameterChanged)
            injection_layout.addWidget(button, 1, i)

        return injection_box

    def metaBox(self):
        meta_box = QtWidgets.QGroupBox('Meta')
        main_layout = QtWidgets.QVBoxLayout()
        meta_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(meta_layout)
        meta_layout.setSpacing(4)
        meta_layout.setContentsMargins(4, 4, 4, 4)
        meta_box.setLayout(main_layout)

        self.meta_params = {
            'span': Knob(1, 30),
            'jump': Knob(0, 12),
            'cDens': Knob(0, 1),
            'cDepth': Knob(1, 5),
            'tCent': Knob(40, 80),
            'rDens': Knob(0, 8),
            'pos': Knob(0, 1),
        }

        for k, v in self.meta_params.items():
            meta_layout.addWidget(v)
            v.setFixedHeight(30)
            v.setFixedWidth(30)
            v.valueChanged.connect(self.parameterChanged)

        random_button = QtWidgets.QPushButton('random')
        random_button.clicked.connect(self.randomMetaData)
        main_layout.addWidget(random_button)

        return meta_box

    def randomMetaData(self):
        for k, v in self.meta_params.items():
            pc = randint(0, 100)/100
            v.value = v.minimum + pc*(v.maximum - v.minimum)

    def setTrackView(self, track_view):
        self._track_view = track_view

    def setSection(self, section_box=None):
        #print('[SectionParameters]', 'setSection', section_box)
        if not section_box:
            return

        self._section_box = section_box
        self._section = section_box.section
        self._instrument = section_box.instrument
        self._section_name.setText(f'{self._instrument.name}: {self._section.name}')

        color = section_box.getSectionColor()
        style_sheet = f'background-color: rgba({color.red()},{color.green()},{color.blue()},255);'
        self._section_name.setStyleSheet(style_sheet)

        params = self._section.params
        for k, v in params.items():
            if k not in self.parameters:
                continue

            self.parameters[k].blockSignals(True)

            if k in {'lead_mode', 'sample_mode', 'context_mode', 'chord_mode'}:
                self.parameters[k].setCurrentText(str(v))
            elif k == 'lead':
                index = self.parameters['lead'].findData(v)
                self.parameters[k].setCurrentIndex(index)
            else:
                self.parameters[k].setValue(v)

            self.parameters[k].blockSignals(False)

        if self._section.type_ == 'fixed':
            for b in ('structure', 'lead', 'sample', 'injection', 'meta'):
                self._boxes[b].hide()
            return
        else:
            for b in self._boxes.values():
                b.show()

        self.lead.blockSignals(True)
        self.lead.clear()
        self.lead.addItem('None', -1)

        for ins in self._engine.instruments.values():
            print(ins, self._instrument)
            if self._instrument.id_ != ins.id_:
                self.lead.addItem(ins.name, ins.id_)

        instrumentID = params['lead']
        if instrumentID != None and instrumentID > -1:
            lead_name = self._engine.instruments[instrumentID].name
            self.lead.setCurrentText(lead_name)
            self.parameters['lead_mode'].setVisible(True)
        else:
            self.lead.setCurrentIndex(0)
            self.parameters['lead_mode'].setVisible(False)
        self.lead.blockSignals(False)

        injection_params = params.get('injection_params', None)
        if injection_params:
            for k, v in self.injection_params.items():
                if k == 'scale':
                    self.injection_params['scale'].setCurrentText(injection_params[1])
                else:
                    if k in injection_params[0]:
                        v.setChecked(True)
                    else:
                        v.setChecked(False)

        meta_data = params.get('meta_data', None)
        if meta_data:
            for k, v in meta_data.items():
                if k in {'ts', 'expression'}:
                    continue
                self.meta_params[k].blockSignals(True)
                self.meta_params[k].value = v
                self.meta_params[k].blockSignals(False)
                self.meta_params[k].update()

        self.setControlBounds()

    def setControlBounds(self):
        if self.loop_num.value() > 1:
            self.loop_alt_len.setVisible(True)
            if self.loop_alt_len.value() > 0:
                self.loop_alt_num.setVisible(True)
            else:
                self.loop_alt_num.setVisible(False)
        else:
            self.loop_alt_num.setVisible(False)
            self.loop_alt_len.setVisible(False)

        self.loop_alt_len.setMaximum(self.length.value()-1)
        self.loop_alt_num.setMaximum(max(2, self.loop_num.value()))

        if self.parameters['lead'].currentData() == -1:
            self.parameters['lead_mode'].setVisible(False)
        else:
            self.parameters['lead_mode'].setVisible(True)

        if self.parameters['context_mode'].currentText() == 'inject':
            for v in self.injection_params.values():
                v.setVisible(True)
        else:
            for v in self.injection_params.values():
                v.setVisible(False)

    def parameterChanged(self, *args):
        if not self._section:
            return

        print('[SectionParameters]', 'parameterChanged')
        params = dict()
        for k, v in self.parameters.items():
            if k in {'lead_mode', 'context_mode', 'sample_mode', 'chord_mode'}:
                params[k] = v.currentText()
                #print(k, v.currentText())
            elif k == 'lead':
                params[k] = v.currentData()
                #print(k, v.currentData())
            elif k == 'note_length':
                params[k] = v.value
            elif k == 'velocity_range':
                params[k] = (v.left, v.right)
            else:
                params[k] = v.value()
                #print(k, v.value())

        scale = 'maj'
        beats = []
        for k, v in self.injection_params.items():
            if k == 'scale':
                scale = v.currentText()
            else:
                if v.isChecked():
                    beats.append(k)

        params['injection_params'] = (tuple(beats), scale)

        meta_data = deepcopy(DEFAULT_META_DATA)
        for k, v in self.meta_params.items():
            meta_data[k] = v.value

        params['meta_data'] = meta_data

        self.setControlBounds()

        self._section.changeParameter(**params)

    def generateMeasures(self, gen_all=False):
        self._instrument.requestGenerateMeasures(self._section.id_, gen_all=gen_all)

    def duplicateSection(self):
        bar_num, section = self._instrument.duplicateSection(self._section.id_)

    def deleteSection(self):
        if self._section_box:
            self._instrument.deleteBlock(self._section_box.block.id_)
            self._track_view.deleteSectionBox(self._instrument.id_, self._section_box.block.id_)


class InstrumentPanel(QtWidgets.QFrame):
    ''' The controls for the instrument '''
    def __init__(self, instrument, engine, track_view, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setFrameStyle(QtWidgets.QFrame.StyledPanel | QtWidgets.QFrame.Plain)

        self.instrument = instrument
        self._engine = engine
        self._track_view = track_view

        self._selected_index = None
        self._selected_id = None

        control_layout = QtWidgets.QGridLayout()
        control_layout.setSpacing(2)
        control_layout.setContentsMargins(2, 2, 2, 2)

        self._instrument_name = self.instrument.name
        #self._instrument_color = QtGui.QColor('#aa0000')
        control_layout.addWidget(QtWidgets.QLabel(self._instrument_name), 0, 0)

        channel_select = QtWidgets.QSpinBox()
        channel_select.setRange(1, 8)
        channel_select.setValue(self.instrument.chan)
        channel_select.valueChanged.connect(self.changeChannel)
        channel_select.setToolTip('Sets the MIDI output channel')
        control_layout.addWidget(channel_select, 0, 1)

        add_section = QtWidgets.QPushButton('+')
        add_section.setToolTip('Add a new section to track')
        add_section.clicked.connect(self.newSection)
        control_layout.addWidget(add_section, 1, 0, 1, 2)

        generate_all = QtWidgets.QPushButton('gen')
        generate_all.setToolTip('Generate all empty measures in all sections')
        generate_all.clicked.connect(self.generateAll)
        control_layout.addWidget(generate_all, 2, 0)

        regenerate_all = QtWidgets.QPushButton('re-gen')
        regenerate_all.setToolTip('Regenerate all measures in all sections')
        regenerate_all.clicked.connect(lambda x: self.generateAll(True))
        control_layout.addWidget(regenerate_all, 2, 1)

        mute = QtWidgets.QPushButton('mute')
        mute.setCheckable(True)
        mute.setChecked(self.instrument.mute)
        mute.setToolTip('Mute the instrument')
        mute.clicked[bool].connect(self.mute)
        control_layout.addWidget(mute, 3, 0)

        octave = QtWidgets.QComboBox()
        octave.setToolTip('Transpose octave')
        octave.addItems(['+3', '+2', '+1', '--', '-1', '-2', '-3'])
        octave.setCurrentIndex(self.instrument.octave_transpose + 3)
        octave.currentTextChanged.connect(self.changeOctave)
        control_layout.addWidget(octave, 3, 1)

        self.instrument.track.addCallback(lambda x: self._track_view.buildSections(self.instrument.id_))
        self.setLayout(control_layout)

    def newSection(self):
        # copy params from last bar
        last_section = self.instrument.track.getLastSection()
        if last_section:
            _, _ = self.instrument.newSection(sectionType='ai', **last_section.params)
        else:
            _, _ = self.instrument.newSection(sectionType='ai', length=4)

    def importMidi(self):
        pass

    def generateAll(self, regen=False):
        self.instrument.requestGenerateMeasures(gen_all=regen)

    def changeChannel(self, new_chan):
        self._engine.changeChannel(self.instrument.id_, new_chan)

    def changeOctave(self, octave):
        new_octave = {'-3': -3, '-2': -2, '-1': -1, '--': 0,
                      '+1': 1, '+2': 2, '+3': 3}[octave]
        self._engine.changeOctaveTranspose(self.instrument.id_, new_octave)

    def mute(self, mute):
        self._engine.changeMute(self.instrument.id_, mute)


class SectionView(QtWidgets.QWidget):
    def __init__(self, engine, *args, **kwargs):
        super(SectionView, self).__init__(*args, **kwargs)

        self.section_layout = QtWidgets.QStackedLayout()

        null_view = QtWidgets.QLabel('No SECTION selected')
        null_view.setLayout(QtWidgets.QHBoxLayout())
        self.section_layout.insertWidget(0, null_view)

        self._section_paramters = SectionParameters(engine)
        self.section_layout.insertWidget(1, self._section_paramters)

        self.setLayout(self.section_layout)

    def setTrackView(self, track_view):
        self._section_paramters.setTrackView(track_view)

    def setSection(self, section_box=None):
        if section_box:
            self._section_paramters.setSection(section_box)
            self.section_layout.setCurrentIndex(1)
        else:
            self.section_layout.setCurrentIndex(0)
