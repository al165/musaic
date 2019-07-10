
#pylint: disable=invalid-name,missing-docstring

import tkinter as tk

from colorsys import hsv_to_rgb

from core import DEFAULT_SECTION_PARAMS

BAR_WIDTH = 80

class PropertyBox(tk.Frame):

    def __init__(self, root, val=None, from_=0, to_=32, callback=None, **kwargs):
        super().__init__(root, **kwargs)

        self.val = val
        self.from_ = from_
        self.to_ = to_

        self.callback = callback

        self.text = tk.Label(self, text=val, width=max(2, len(str(to_))), anchor='e')
        self.text.grid(row=0, column=0)

        buttons = tk.Canvas(self, width=10, height=16)
        buttons.create_rectangle(0, 0, 10, 8, activefill='#555555')
        buttons.create_rectangle(0, 11, 10, 16, activefill='#555555')
        buttons.bind('<Button-1>', self.onClick)

        buttons.create_polygon(1, 6, 5, 1, 9, 6, fill='white')
        buttons.create_polygon(1, 10, 5, 15, 9, 10, fill='white')

        buttons.grid(row=0, column=1)

        if val:
            self.set(val, call=False)
        else:
            self.val = self.from_

    def onClick(self, event):
        if 0 < event.y < 8:
            self.increment()
        elif 8 < event.y < 16:
            self.decrement()

    def set(self, val, call=True):
        if val < self.from_:
            self.val = self.from_
        elif val > self.to_:
            self.val = self.to_
        else:
            self.val = val

        self.text.config(text=self.val)

        if self.callback and call:
            self.callback()

    def get(self):
        return self.val

    def increment(self, call=True):
        self.set(self.val+1, call=call)

    def decrement(self, call=True):
        self.set(self.val-1, call=call)


class TimeLine(tk.Frame):

    def __init__(self, root, instrumentPanels, engine, **kwargs):
        super().__init__(root, **kwargs)

#        self.instruments = instruments
        self.instrumentPanels = instrumentPanels
        self.engine = engine

        self.timelineFrame = tk.Frame(root)
        self.timelineFrame.grid(row=1, column=1, sticky='ew')
        self.timelineCanvas = tk.Canvas(self.timelineFrame, width=800, height=16, bg='grey')
        self.timelineCanvas.grid(row=0, column=0, sticky='ew')

        self.timelineCursor = self.timelineCanvas.create_line(0, 0, 0, 16, width=3, fill='orange')

        self.hsb = tk.Scrollbar(self.timelineFrame, orient='horizontal', command=self.scrollTracks)
        self.hsb.grid(row=1, column=0, sticky='ew')

        self.timelineCanvas.config(xscrollcommand=self.hsb.set)
        self.timelineCanvas.bind('<Button-1>', self.onClick)

    def updateCanvas(self):
        cursorCoords = self.timelineCanvas.coords(self.timelineCursor)
        self.timelineCanvas.delete('all')

        # find largest bounding box
        n = max([len(p.instrument) for p in self.instrumentPanels] + [0])

        for i in range(n+1):
            x = i * 80
            self.timelineCanvas.create_text(x, 7, text='{:>3}'.format(i), anchor='w')
            self.timelineCanvas.create_line(x, 0, x, 20)

        self.timelineCursor = self.timelineCanvas.create_line(cursorCoords, width=3, fill='orange')

        scrollRegion = self.timelineCanvas.bbox('all')
        self.timelineCanvas.config(scrollregion=scrollRegion)

        for p in self.instrumentPanels:
            p.trackCanvas.config(scrollregion=scrollRegion)

    def updateCursor(self, barNum, tick):
        x = (barNum + tick/96) * 80
        if self.timelineCursor:
            self.timelineCanvas.coords(self.timelineCursor, (x, 0, x, 16))
        else:
            self.timelineCursor = self.timelineCanvas.create_line(x, 0, x, 16, width=3, fill='orange')

    def scrollTracks(self, *args):
        self.timelineCanvas.xview(*args)
        for p in self.instrumentPanels:
            p.trackCanvas.xview(*args)

    def onClick(self, event):
        x = self.timelineCanvas.canvasx(event.x)
        barNum = int(x/BAR_WIDTH)
        print(barNum)
        self.engine.setBarNumber(barNum)

class InstrumentPanel():

    def __init__(self, root, instrument, engine, timeline, **kwargs):
        self.id_ = instrument.id_

        self.instrument = instrument
        self.engine = engine
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
            'length': PropertyBox(sectionParams, from_=1, to_=32, callback=self.setParameter),
            'loop_num': PropertyBox(sectionParams, from_=1, to_=64, callback=self.setParameter),
            'loop_alt_num': PropertyBox(sectionParams, from_=2, to_=8, callback=self.setParameter),
            'loop_alt_len': PropertyBox(sectionParams, from_=0, to_=32, callback=self.setParameter),
        }

        self.paramVars['name'].grid(row=0, column=0, columnspan=4, sticky='ew')
        self.paramVars['length'].grid(row=1, column=0, sticky='ew')
        self.paramVars['loop_num'].grid(row=1, column=1, sticky='ew')
        self.paramVars['loop_alt_num'].grid(row=1, column=2, sticky='ew')
        self.paramVars['loop_alt_len'].grid(row=1, column=3, sticky='ew')

        regenerateButton = tk.Button(sectionParams, text='reg',
                                     command=self.regenerateMeasures)
        regenerateButton.grid(row=0, column=5, rowspan=2)

        trackFrame = tk.Frame(root)
        trackFrame.grid(row=self.id_+2, column=1, sticky='ew')
        self.trackCanvas = tk.Canvas(trackFrame, width=800, height=80)
        self.trackCanvas.grid(row=0, column=0, sticky='nesw')

        self.trackCursor = self.trackCanvas.create_line(0, 0, 0, 80, width=3, fill='orange')

        self.sectionFrames = dict()
        self.sectionBlocksColors = dict()

    def newSection(self):
        section = self.instrument.newSection()
        sectionID = section.id_
        hue = (sectionID * 0.16) % 1.0
        r, g, b = hsv_to_rgb(hue, 0.8, 0.5)
        hexColor = f'#{hex(int(r*255))[2:]}{hex(int(g*255))[2:]}{hex(int(b*255))[2:]}'
        self.sectionBlocksColors[sectionID] = hexColor
        self.selectSection(sectionID, len(self.instrument.track.track)-1)
        self.updateCanvas()

    def newBlankSection(self):
        section = self.instrument.newSection(blank=True)
        sectionID = section.id_
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
        if self.selectedIndex == idx:
            return

        try:
            self.trackCanvas.itemconfig(self.sectionFrames[self.selectedIndex], outline='black')
        except KeyError:
            pass

        self.selectedSection = self.instrument.sections[id_]
        self.selectedIndex = idx

        try:
            self.trackCanvas.itemconfig(self.sectionFrames[self.selectedIndex], outline='white')
        except KeyError:
            pass

        self.paramVars['name'].config(text=self.selectedSection.name,
                                      bg=self.sectionBlocksColors[id_])
        for param, var in self.paramVars.items():
            if param == 'name':
                continue
            var.set(self.selectedSection.params[param], call=False)

    def updateCanvas(self):
        ''' TODO: Make more efficient! '''

        print('canvas updated')
        x = 0
        cursorCoords = self.trackCanvas.coords(self.trackCursor)
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
                if m:
                    for note in m.notes:
                        if note[0] <= 0:
                            continue
                        xOn = x + i*barWidth + tickWidth*note[1]
                        xOff = x + i*barWidth + tickWidth*note[2]
                        self.trackCanvas.create_line(xOn, height-note[0],
                                                     xOff-1, height-note[0], fill='#555555')

                    self.trackCanvas.create_text(x + (i+1)*barWidth - 7, 25, text=m.id_)

                if (not m or m.isEmpty()) and not s.blank:
                    # draw some indicator of Null bar...
                    self.trackCanvas.create_text(x+i*barWidth+7, 25, text='x', fill='red')
                    continue


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

        #self.trackCanvas.tag_raise(self.trackCursor)
        self.trackCursor = self.trackCanvas.create_line(cursorCoords, width=3, fill='orange')
        self.timeline.updateCanvas()

    def updateCursor(self, barNum, tick):
        x = (barNum + tick/96) * 80
        if self.trackCursor:
            self.trackCanvas.coords(self.trackCursor, (x, 0, x, 80))
        else:
            self.trackCursor = self.trackCanvas.create_line(x, 0, x, 80, width=3, fill='orange')

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

            newParams[param] = val

        self.instrument.changeSectionParameters(self.selectedSection.id_, **newParams)
        self.updateCanvas()

    def regenerateMeasures(self, *args):
        if self.selectedSection:
            self.selectedSection.generateMeasures()
        self.instrument.track.flattenMeasures()
        self.updateCanvas()

    def moveSectionLeft(self):
        self.instrument.track.moveSectionBack(self.selectedIndex)
        if self.selectedIndex > 0:
            self.selectedIndex -= 1
        self.updateCanvas()

#EOF
