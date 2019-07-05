
#pylint: disable=invalid-name,missing-docstring

import tkinter as tk
from colorsys import hsv_to_rgb

from core import Instrument

class TimeLine(tk.Frame):

    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)

        self.timelineFrame = tk.Frame(root)
        self.timelineFrame.grid(row=1, column=1, sticky='ew')
        self.timeLineCanvas = tk.Canvas(self.timelineFrame, width=800, height=20, bg='grey')
        self.timeLineCanvas.grid(row=0, column=0, sticky='ew')

        self.hsb = tk.Scrollbar(self.timelineFrame, orient='horizontal', command=self.scrollTracks)
        self.hsb.grid(row=1, column=0, sticky='ew')

        self.timeLineCanvas.config(xscrollcommand=self.hsb.set)

        self.trackCanvases = []

    def addTrack(self, trackCanvas):
        self.trackCanvases.append(trackCanvas)

    def updateCanvas(self, n):
        self.timeLineCanvas.delete('all')
        for i in range(n):
            x = i * 80
            self.timeLineCanvas.create_text(x, 5, text='{:>3}'.format(i))
            self.timeLineCanvas.create_line(x, 0, x, 20)

        self.timeLineCanvas.config(scrollregion=self.timeLineCanvas.bbox('all'))

    def scrollTracks(self, *args):
        self.timeLineCanvas.xview(*args)
        for c in self.trackCanvases:
            c.xview(*args)



class InstrumentPanel():

    def __init__(self, root, instrument, timeline, **kwargs):
        #super().__init__(root, **kwargs)
        #self.config(relief='sunken', bd=1)

        self.id_ = instrument.id_

        self.instrument = instrument
        self.timeline = timeline

        self.selectedSection = None
        self.selectedIndex = 0

        self.controls = tk.Frame(root)
        self.controls.grid(row=self.id_+2, column=0)

        nameLabel = tk.Label(self.controls, text=self.instrument.name)
        nameLabel.grid(row=0, column=0)
        addSectionButton = tk.Button(self.controls, text='new section', command=self.newSection)
        addSectionButton.grid(row=0, column=1)

        self.sectionParams = tk.Frame(self.controls, bd=2, relief='sunken')
        self.sectionParams.grid(row=1, column=0, columnspan=2)

        self.sectionName = tk.Label(self.sectionParams, text='')
        self.sectionName.grid(row=0, column=0)
        self.sectionLengthVar = tk.IntVar(self.sectionParams)
        self.sectionLengthVar.trace('w', self.setLength)
        self.sectionLength = tk.Spinbox(self.sectionParams, from_=0, to=128,
                                        textvariable=self.sectionLengthVar, width=3)
        self.sectionLength.grid(row=0, column=1)
        moveLeftButton = tk.Button(self.sectionParams, text='<', command=self.moveSectionLeft)
        moveLeftButton.grid(row=0, column=2)
        duplicateSectionButton = tk.Button(self.sectionParams, text='=',
                                           command=self.duplicateSection)
        duplicateSectionButton.grid(row=0, column=3)

        self.trackFrame = tk.Frame(root)
        self.trackFrame.grid(row=self.id_+2, column=1, sticky='ew')
        self.trackCanvas = tk.Canvas(self.trackFrame, width=800, height=80)
        self.trackCanvas.grid(row=0, column=0, sticky='ew')

        self.hsb = tk.Scrollbar(self.trackFrame, orient='horizontal', command=self.trackCanvas.xview)
        self.hsb.grid(row=1, column=0, sticky='ew')

        self.trackCanvas.config(xscrollcommand=self.hsb.set)

        self.sectionBlocksColors = {}

    def newSection(self):
        self.instrument.newSection()
        sectionID = self.instrument.sections[-1]._id
        hue = (sectionID * 0.16) % 1.0
        r, g, b = hsv_to_rgb(hue, 0.8, 0.5)
        hexColor = f'#{hex(int(r*255))[2:]}{hex(int(g*255))[2:]}{hex(int(b*255))[2:]}'
        self.sectionBlocksColors[sectionID] = hexColor
        self.selectSection(sectionID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def duplicateSection(self):
        selectedID = self.selectedSection._id
        self.instrument.duplicateSection(selectedID)
        self.selectSection(selectedID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def selectSection(self, id_, idx):
        print('Selected', id_, idx)
        self.selectedSection = self.instrument.sections[id_]
        self.selectedIndex = idx
        self.sectionName.config(text=self.selectedSection.name)
        self.sectionLengthVar.set(self.selectedSection.params['length'])

    def updateCanvas(self):
        x = 0
        self.trackCanvas.delete('all')
        for idx, s in enumerate(self.instrument.track.track):
            w = len(s) * 80
            sID = s._id
            section = self.trackCanvas.create_rectangle(x, 0, x + w, 60,
                                                        fill=self.sectionBlocksColors[sID],
                                                        tags=(str(sID), str(idx)),
                                                        outline='black')

            if idx == self.selectedIndex:
                self.trackCanvas.itemconfig(section, outline='white')

            self.trackCanvas.tag_bind(section, '<Button-1>', self.onClick)

            x += w

        self.trackCanvas.config(scrollregion=self.trackCanvas.bbox('all'))

        self.timeline.updateCanvas(len(self.instrument))

    def onClick(self, event):
        section = self.trackCanvas.find_closest(event.x, event.y)
        tags = self.trackCanvas.itemcget(section, 'tags').split()
        self.selectSection(int(tags[0]), int(tags[1]))

    def setLength(self, *args):
        if not self.selectedSection:
            return

        try:
            val = int(self.sectionLengthVar.get())
        except ValueError:
            self.sectionLengthVar.set(4)
            return

        if val < 1:
            self.sectionLengthVar.set(1)
            return

        self.selectedSection.changeParameter(length=val)
        self.updateCanvas()

    def moveSectionLeft(self):
        self.instrument.track.moveSectionBack(self.selectedIndex)
        if self.selectedIndex > 0:
            self.selectedIndex -= 1
        self.updateCanvas()


class MusaicApp:

    def __init__(self):
        self.root = tk.Tk()
        self.mainframe = tk.Frame(self.root)
        self.mainframe.pack()

        addInsButton = tk.Button(self.mainframe, text='+', command=self.addInstrument)
        addInsButton.grid(row=0, column=0, sticky='ew')

        self.timeLine = TimeLine(self.mainframe)
        #self.timeLine.grid(row=1, column=1, sticky='ew')

        self.instruments = []
        self.instrumentPanels = []

        self.root.mainloop()


    def addInstrument(self):
        id_ = len(self.instruments)
        instrument = Instrument(id_, 'INS ' + str(id_), 1)
        panel = InstrumentPanel(self.mainframe, instrument, self.timeLine)
        #panel.grid(row=len(self.instruments) + 1, column=0)

        self.instruments.append(instrument)
        self.instrumentPanels.append(panel)

        self.timeLine.addTrack(panel.trackCanvas)



if __name__ == '__main__':
    app = MusaicApp()
