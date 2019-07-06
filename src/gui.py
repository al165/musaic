
#pylint: disable=invalid-name,missing-docstring

import tkinter as tk

from colorsys import hsv_to_rgb

from core import DEFAULT_SECTION_PARAMS


def changeVarWithoutCallback(var, val):
    ''' Changes a tk Variable without evoking any callbacks'''
    

class TimeLine(tk.Frame):

    def __init__(self, root, instrumentPanels, **kwargs):
        super().__init__(root, **kwargs)

#        self.instruments = instruments
        self.instrumentPanels = instrumentPanels

        self.timelineFrame = tk.Frame(root)
        self.timelineFrame.grid(row=1, column=1, sticky='ew')
        self.timelineCanvas = tk.Canvas(self.timelineFrame, width=800, height=16, bg='grey')
        self.timelineCanvas.grid(row=0, column=0, sticky='ew')

        self.hsb = tk.Scrollbar(self.timelineFrame, orient='horizontal', command=self.scrollTracks)
        self.hsb.grid(row=1, column=0, sticky='ew')

        self.timelineCanvas.config(xscrollcommand=self.hsb.set)

    def updateCanvas(self):
        self.timelineCanvas.delete('all')

        # find largest bounding box
        n = max([len(p.instrument) for p in self.instrumentPanels] + [0])

        for i in range(n+1):
            x = i * 80
            self.timelineCanvas.create_text(x, 7, text='{:>3}'.format(i), anchor='w')
            self.timelineCanvas.create_line(x, 0, x, 20)

        scrollRegion = self.timelineCanvas.bbox('all')
        self.timelineCanvas.config(scrollregion=scrollRegion)

        for p in self.instrumentPanels:
            p.trackCanvas.config(scrollregion=scrollRegion)

    def scrollTracks(self, *args):
        self.timelineCanvas.xview(*args)
        for p in self.instrumentPanels:
            p.trackCanvas.xview(*args)


class InstrumentPanel():

    def __init__(self, root, instrument, timeline, **kwargs):
        self.id_ = instrument.id_

        self.instrument = instrument
        self.timeline = timeline

        self.selectedSection = None
        self.selectedIndex = -1

        # Instrument controls
        controls = tk.Frame(root, **kwargs)
        controls.grid(row=self.id_+2, column=0, sticky='nsew')

        deleteButton = tk.Button(controls, text='x')
        deleteButton.grid(row=0, column=0)
        nameLabel = tk.Label(controls, text=self.instrument.name)
        nameLabel.grid(row=0, column=1, columnspan=2)
        chanLabel = tk.Label(controls, text='1')
        chanLabel.grid(row=0, column=3)
        addSectionButton = tk.Button(controls, text='+', command=self.newSection)
        addSectionButton.grid(row=1, column=0)
        duplicateSectionButton = tk.Button(controls, text='=',
                                           command=self.duplicateSection)
        duplicateSectionButton.grid(row=1, column=1)
        addBlankButton = tk.Button(controls, text='_', command=self.newBlankSection)
        addBlankButton.grid(row=1, column=2)
        moveLeftButton = tk.Button(controls, text='<', command=self.moveSectionLeft)
        moveLeftButton.grid(row=1, column=3)

        # Selected section controls
        sectionParams = tk.Frame(controls, bd=2, relief='sunken')
        sectionParams.grid(row=2, column=0, columnspan=4, sticky='nsew')

        self.paramVars = {
            'name': tk.Label(sectionParams, text=''),
            'length': tk.IntVar(sectionParams),
            'loop_num': tk.IntVar(sectionParams),
            'loop_alt_num': tk.IntVar(sectionParams),
            'loop_alt_len': tk.IntVar(sectionParams)
        }

        self.paramVars['name'].grid(row=0, column=0)

        for param, var in self.paramVars.items():
            if param == 'name':
                continue
            var.trace('w', self.setParameter)

        sectionLength = tk.Spinbox(sectionParams, from_=1, to=128,
                                   textvariable=self.paramVars['length'], width=3)
        sectionLength.grid(row=0, column=1)

        sectionLoopNum = tk.Spinbox(sectionParams, from_=1, to=128,
                                    textvariable=self.paramVars['loop_num'], width=3)
        sectionLoopNum.grid(row=0, column=2)

        sectionLoopAltLen = tk.Spinbox(sectionParams, from_=0, to=128,
                                       textvariable=self.paramVars['loop_alt_len'], width=3)
        sectionLoopAltLen.grid(row=0, column=3)

        sectionLoopAltNum = tk.Spinbox(sectionParams, from_=2, to=8,
                                       textvariable=self.paramVars['loop_alt_num'], width=3)
        sectionLoopAltNum.grid(row=0, column=4)

        regenerateButton = tk.Button(sectionParams, text='regenerate',
                                     command=self.regenerateMeasures)
        regenerateButton.grid(row=1, column=0, columnspan=5)

        trackFrame = tk.Frame(root)
        trackFrame.grid(row=self.id_+2, column=1, sticky='ew')
        self.trackCanvas = tk.Canvas(trackFrame, width=800, height=80)
        self.trackCanvas.grid(row=0, column=0, sticky='nesw')

        self.trackCursor = self.trackCanvas.create_line(20, 0, 20, 80, width=3, fill='orange')

        self.sectionFrames = dict()
        self.sectionBlocksColors = {}

    def newSection(self):
        self.instrument.newSection()
        sectionID = self.instrument.sections[-1].id_
        hue = (sectionID * 0.16) % 1.0
        r, g, b = hsv_to_rgb(hue, 0.8, 0.5)
        hexColor = f'#{hex(int(r*255))[2:]}{hex(int(g*255))[2:]}{hex(int(b*255))[2:]}'
        self.sectionBlocksColors[sectionID] = hexColor
        self.selectSection(sectionID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def newBlankSection(self):
        self.instrument.newBlankSection()
        sectionID = self.instrument.sections[-1].id_
        hexColor = '#222222'
        self.sectionBlocksColors[sectionID] = hexColor
        self.selectSection(sectionID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def duplicateSection(self):
        selectedID = self.selectedSection.id_
        self.instrument.duplicateSection(selectedID)
        self.selectSection(selectedID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def selectSection(self, id_, idx):
        #print('Selected', id_, idx)
        if self.selectedIndex == idx:
            return

        try:
            self.trackCanvas.itemconfig(self.sectionFrames[self.selectedIndex], outline='black')
        except KeyError:
            pass

        self.selectedSection = self.instrument.sections[id_]
        self.selectedIndex = idx
        self.paramVars['name'].config(text=self.selectedSection.name)
        for param, var in self.paramVars.items():
            if param == 'name':
                continue
            var.set(self.selectedSection.params[param])

        #self.trackCanvas.itemconfig(self.sectionFrames[idx], outline='white')

    def updateCanvas(self):
        ''' TODO: Make more efficient! '''

        print('canvas updated')
        x = 0
        self.trackCanvas.delete('all')
        self.sectionFrames = dict()
        height = 80
        barWidth = 80
        for idx, s in enumerate(self.instrument.track.track):
            w = len(s) * barWidth
            mainWidth = s.mainLength() * barWidth
            sID = s.id_

            # Draw section block...
            self.trackCanvas.create_rectangle(x, 0, x+w-1, 20,
                                              fill=self.sectionBlocksColors[sID],
                                              outline='black')

            self.trackCanvas.create_text(x+7, 5, text=s.name,
                                         anchor='nw', fill='black')

            self.trackCanvas.create_rectangle(x, 20, x+w-1, height,
                                              fill='#333333', outline='black')

            for i in range(1, len(s)):
                x2 = x + i*barWidth
                if i % s.mainLength() == 0:
                    self.trackCanvas.create_line(x2, 0, x2, height, fill='#111111', width=2)
                elif (i+s.params['loop_alt_len']) % s.mainLength() == 0:
                    self.trackCanvas.create_line(x2, 10, x2, height, fill='#111111')
                    self.trackCanvas.create_line(x2, 10, x2 + s.params['loop_alt_len']*barWidth,
                                                 10, fill='#111111')
                else:
                    self.trackCanvas.create_line(x2, 20, x2, height, fill='#111111')

            # Draw notes...
            tickWidth = barWidth/96
            for i, m in enumerate(s.flatMeasures):
                if not m:
                    # draw some indicator of Null bar...
                    self.trackCanvas.create_text(x+i*barWidth+7, 25, text='x', fill='red')
                    continue

                for note in m.notes:
                    xOn = x + i*barWidth + tickWidth*note[1]
                    xOff = x + i*barWidth + tickWidth*note[2]
                    y = note[0]
                    self.trackCanvas.create_line(xOn, y, xOff-1, y, fill='#555555')

            # Fade repeated parts...
            self.trackCanvas.create_rectangle(x+mainWidth, 0, x+w-1, height, width=0,
                                              fill='black', stipple='gray25')
            # Draw border...
            sectionFrame = self.trackCanvas.create_rectangle(x, 0, x+w-1, height-1,
                                                             fill='#ff0000',
                                                             stipple='@transparent.xmb',
                                                             tags=(str(sID), str(idx)))

            self.sectionFrames[idx] = sectionFrame
            if idx == self.selectedIndex:
                self.trackCanvas.itemconfig(sectionFrame, outline='white')

            self.trackCanvas.bind('<Button-1>', self.onClick)

            x += w

        self.trackCanvas.tag_raise(self.trackCursor)
        self.timeline.updateCanvas()

    def onClick(self, event):
        x = self.trackCanvas.canvasx(event.x)
        section = self.trackCanvas.find_closest(x, 10)
        tags = self.trackCanvas.itemcget(section, 'tags').split()
        #print(tags)
        if len(tags) < 2:
            return
        self.selectSection(int(tags[0]), int(tags[1]))

    def setParameter(self, *args):
        if not self.selectedSection:
            return

        newParams = dict()
        for param, var in self.paramVars.items():
            if param == 'name':
                continue
            try:
                val = int(var.get())
            except ValueError:
                val = DEFAULT_SECTION_PARAMS[param]

            if val < 0:
                val = 1

            newParams[param] = val

        self.selectedSection.changeParameter(**newParams)
        self.updateCanvas()

    def regenerateMeasures(self, *args):
        if self.selectedSection:
            self.selectedSection.generateMeasures()
        self.updateCanvas()

    def moveSectionLeft(self):
        self.instrument.track.moveSectionBack(self.selectedIndex)
        if self.selectedIndex > 0:
            self.selectedIndex -= 1
        self.updateCanvas()
