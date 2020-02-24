import math

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QTimer

class BoxSlider(QtWidgets.QFrame):
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.valueChanged.connect(self.repaint)

        self.setObjectName("QBoxSlider")

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )

        self.setMinimumHeight(10)
        self.setMinimumWidth(30)

        self._forground_color = QtGui.QColor('#5A5A5A')
        self._text_color = None

        self._minimum = 0
        self._maximum = 100

        self._value = 0

        self._show_text = True


    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        self._value = max(min(int(new_value), self.maximum), self.minimum)
        self.valueChanged.emit(self._value)
        self.repaint()

    def setValue(self, new_value):
        self.value = new_value

    @property
    def minimum(self):
        return self._minimum

    def setMinimum(self, minimum):
        self._minimum = int(minimum)
        if self._minimum > self.value:
            self.value = self.minimum

    @property
    def maximum(self):
        return self._maximum

    def setMaximum(self, maximum):
        self._maximum = int(maximum)
        if self._maximum < self.value:
            self.value = self.maximum

    def setRange(self, minimum, maximum):
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def setShowText(self, show):
        self._show_text = show

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)

        brush = QtGui.QBrush()
        brush.setColor(self._forground_color)
        brush.setStyle(Qt.SolidPattern)

        width = painter.device().width()
        height = painter.device().height()

        percent = (self.value - self.minimum) / (self.maximum - self.minimum)

        rect = QtCore.QRect(0, 0, width*percent, height)
        painter.fillRect(rect, brush)

        if self._text_color:
            painter.setPen(self._text_color)

        if self._show_text:
            rect = QtCore.QRect(0, 0, width, height)
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignHCenter, str(f'{self.value}'))

        painter.end()

    def _calculate_clicked_value(self, e):
        vmin, vmax = self.minimum, self.maximum
        width = self.size().width()
        click_x = e.x()
        pc = click_x / width

        value = int(vmin+pc*(vmax - vmin))
        self.value = value

    def mouseMoveEvent(self, e):
        self._calculate_clicked_value(e)

    def mousePressEvent(self, e):
        self._calculate_clicked_value(e)


class BoxRangeSlider(QtWidgets.QFrame):
    rangeChanged = QtCore.pyqtSignal(int, int)

    def __init__(self, minimum=0, maximum=128, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setObjectName("QBoxRangeSlider")

        self.setSizePolicy(
            QtWidgets.QSizePolicy.MinimumExpanding,
            QtWidgets.QSizePolicy.MinimumExpanding
        )

        self.setMinimumHeight(10)
        self.setMinimumWidth(30)

        self._forground_color = QtGui.QColor('#5A5A5A')
        self._text_color = None

        self._minimum = minimum
        self._maximum = maximum

        self._left = minimum
        self._right = maximum

        self._show_text = True

        self.rangeChanged.connect(self.repaint)

    def setValue(self, r):
        self.left = r[0]
        self.right = r[1]

    @property
    def left(self):
        return self._left

    @left.setter
    def left(self, new_left):
        if new_left >= self.right:
            new_left = self.right
        self._left = max(int(new_left), self.minimum)
        self.rangeChanged.emit(self.left, self.right)
        self.repaint()

    @property
    def right(self):
        return self._right

    @right.setter
    def right(self, new_right):
        self._right = min(int(new_right), self.maximum)
        self.rangeChanged.emit(self._left, new_right)
        self.repaint()

    @property
    def minimum(self):
        return self._minimum

    def setMinimum(self, minimum):
        self._minimum = int(minimum)
        if self._minimum > self.left:
            self.left = self._minimum

    @property
    def maximum(self):
        return self._maximum

    def setMaximum(self, maximum):
        self._maximum = int(maximum)
        if self._maximum < self.right:
            self.right = self._maximum

    def setRange(self, minimum, maximum):
        self.setMinimum(minimum)
        self.setMaximum(maximum)

    def setShowText(self, show):
        self._show_text = show

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)

        brush = QtGui.QBrush()
        brush.setColor(self._forground_color)
        brush.setStyle(Qt.SolidPattern)

        width = painter.device().width()
        height = painter.device().height()

        left_percent = (self.left - self.minimum) / (self.maximum - self.minimum)
        right_percent = (self.right - self.minimum) / (self.maximum - self.minimum)

        rect = QtCore.QRect(width*left_percent, 0, width*(right_percent - left_percent), height)
        painter.fillRect(rect, brush)

        if self._text_color:
            painter.setPen(self._text_color)

        if self._show_text:
            rect = QtCore.QRect(0, 0, width, height)
            painter.drawText(rect, Qt.AlignVCenter | Qt.AlignHCenter, str(f'{self.left}, {self.right}'))

        painter.end()

    def _calculate_clicked_value(self, e):
        vmin, vmax = self.minimum, self.maximum
        width = self.size().width()
        click_x = e.x()
        pc = click_x / width

        mid = (self.left + self.right) / 2
        value = int(vmin+pc*(vmax - vmin))

        if value < mid:
            self.left = value
        else:
            self.right = value

    def mouseMoveEvent(self, e):
        self._calculate_clicked_value(e)

    def mousePressEvent(self, e):
        self._calculate_clicked_value(e)


class Knob(QtWidgets.QWidget):
    valueChanged = QtCore.pyqtSignal(float)

    def __init__(self, minimum=0, maximum=10, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._sensitivity = 200

        self._emit = True
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self.updateValue)

        self._value = minimum
        self.valueChanged.connect(self.repaint)

        self._minimum = minimum
        self._maximum = maximum

        self.minimum = minimum
        self.maximum = maximum
        self.value = minimum

        self._color = QtGui.QColor('#5A5A5A')


    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_val):
        self._value = max(min(new_val, self.maximum), self.minimum)
        if self._emit:
            self.valueChanged.emit(self.value)

    @property
    def minimum(self):
        return self._minimum

    @minimum.setter
    def minimum(self, new_min):
        if self.value < new_min:
            self.value = new_min
        self._minimum = new_min

    @property
    def maximum(self):
        return self._maximum

    @maximum.setter
    def maximum(self, new_max):
        if self.value > new_max:
            self.value = new_max
        self._maximum = new_max

    def setRange(self, new_min, new_max):
        self.minimum = new_min
        self.maximum = new_max

    def paintEvent(self, e):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = painter.device().rect()

        radius = min(rect.width(), rect.height())/2

        pc = (self.value - self.minimum) / (self.maximum - self.minimum)

        a = 4.18879 - pc*5.23599
        x = math.cos(a) * (radius-1) + radius
        y = -math.sin(a) * (radius-1) + radius

        pen = QtGui.QPen()
        pen.setWidth(2)
        pen.setColor(self._color)
        painter.setPen(pen)
        painter.drawArc(1, 1, 2*radius-1, 2*radius-1, -120*16, -300*16)
        pen.setColor(QtGui.QColor('#DDDDDD'))
        painter.setPen(pen)
        painter.drawLine(radius, radius, x, y)

    def setSensitivity(self, s):
        self._sensitivity = s

    def mousePressEvent(self, e):
        self._start_y = e.y()
        self._start_value = self.value
        self._emit = False

    def mouseMoveEvent(self, e):
        dy = self._start_y - e.y()
        r = self.maximum - self.minimum

        self.value = self._start_value + (dy*r)/self._sensitivity
        self.update()

    def mouseReleaseEvent(self, e):
        self._emit = True
        self.value = self.value

    def wheelEvent(self, e):
        change = (1 if e.angleDelta().y() > 0 else -1) * (self.maximum - self.minimum)/100
        self._emit = False
        self.value += change
        self._update_timer.start(100)
        self.update()
        #self.value += change

    def updateValue(self, *args):
        '''When Knob movement has settled, update the value.'''
        self._emit = True
        self.value = self._value



if __name__ == '__main__':
    print(' === TESTING GUI ELEMENTS ===')
    app = QtWidgets.QApplication([])

    window = QtWidgets.QMainWindow()
    window.setGeometry(20, 40, 100, 80)

    main = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout()
    main.setLayout(layout)
    window.setCentralWidget(main)

    slider = BoxSlider()
    slider.setRange(0, 200)
    #layout.addWidget(slider)
    slider.setValue(100)

    rangeSlider = BoxRangeSlider()
    rangeSlider.setRange(50, 150)
    #layout.addWidget(rangeSlider)
    rangeSlider.setValue((75, 100))
    rangeSlider.left = 60

    knob = Knob()
    knob.setRange(0, 1)
    knob.valueChanged.connect(print)
    layout.addWidget(knob)

    window.show()

    app.exec_()

