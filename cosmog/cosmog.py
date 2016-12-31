
import sys
from bisect import bisect_left

import pywt
import kplr
import numpy as np
import pyqtgraph as pg
import pyqtgraph.console
from pyqtgraph.Qt import QtGui as qt
from PyQt5.QtCore import Qt
from scipy import signal
from scipy.misc import imresize
import scipy as sp

class PlanetDialog(qt.QDialog):
    def __init__(self, parent = None):
        super(PlanetDialog, self).__init__(parent)

        layout = qt.QVBoxLayout(self)

        self.planet = qt.QLineEdit(self)
        self.start = qt.QLineEdit(self)
        self.stop = qt.QLineEdit(self)
        layout.addWidget(self.planet)
        layout.addWidget(self.start)
        layout.addWidget(self.stop)

        self.buttons = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel,
            Qt.Horizontal, self)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

    def accept(self, *args):
        print(args)


class PlanetGraph(qt.QWidget):

    def __init__(self, planet, start=0, stop=-1):
        super().__init__()
        self.setupModel(planet, start, stop)
        self.setupGrid()
        self.setupLightCurve()
        self.setupTargetPixels()
        self.setupSpectrumPlot()
        self.loadLightCurves()
        self.loadTargetPixels()
        self.setupRegion()
        self.setupCrosshair()
        self.setupConsole()

    def setupModel(self, planet, start, stop):
        self.client = kplr.API()
        self.planet = self.client.planet(planet)
        self.curve_data = self.planet.get_light_curves()
        self.tpfs = self.planet.get_target_pixel_files()
        self.start = start
        self.stop = stop

    def setupGrid(self):
        self.grid = qt.QGridLayout()
        self.setLayout(self.grid)

    def setupLightCurve(self):
        self.light_curve = pg.PlotWidget(name=self.planet.kepler_name)
        self.light_curve.setDownsampling(auto=True, mode='subsample')
        self.light_curve.setClipToView(True)
        self.light_curve.showGrid(x=True, y=True)
        self.light_curve.showButtons()
        self.label = pg.LabelItem(justify='right')
        self.light_curve.addItem(self.label)
        self.light_curve.setAutoVisible(y=True)
        self.grid.addWidget(self.light_curve, 0, 0, 1, 3)

    def loadLightCurves(self):
        self.all_time = []
        self.all_data = []
        for li, lc in enumerate(self.curve_data[self.start:self.stop]):
            with lc.open() as f:
                data = f[1].data
            time = data['time']
            sapflux = data['sap_flux']
            pdcflux = data['pdcsap_flux']
            qual = data['sap_quality']
            bkg = data['sap_bkg']

            m = np.isfinite(time) * np.isfinite(pdcflux)
            mu = np.median(pdcflux[m])
            norm = (pdcflux[m] / mu - 1) * 1e6

            # corrected flux and background noise
            self.light_curve.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=pg.mkBrush(li))
            self.light_curve.plot(time, bkg, pen=pg.mkPen('y'))
            self.spectrum.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=pg.mkBrush(li))
            self.light_curve.enableAutoRange('y', 0.97)
            self.all_time.append(time[m])
            self.all_data.append(pdcflux[m])

        self.all_time = np.concatenate(self.all_time)
        self.all_norm = np.concatenate(self.all_data)

    def setupSpectrumPlot(self):
        self.spectrum = pg.PlotWidget()
        self.grid.addWidget(self.spectrum, 1, 0, 1, 3)

    def setupTargetPixels(self):
        self.pixels = pg.ImageView()
        self.grid.addWidget(self.pixels, 1, 3)

    def setupConsole(self):
        self.console = pyqtgraph.console.ConsoleWidget(
            namespace=dict(
                planet=self.planet,
                np=np,
                pg=pg,
                sp=sp,
                signal=signal,
                lc=self.light_curve,
                res=self.spectrum,
                tps=self.pixels,
                all_norm=self.all_norm,
                all_flux=self.all_flux,
                all_time=self.all_time,
                all_data=self.all_data,
            ))
        self.grid.addWidget(self.console, 0, 3)

    def loadTargetPixels(self):
        self.all_flux = []
        for ti, tpf in enumerate(self.tpfs[self.start:self.stop]):
            with tpf.open() as f:
                data = f[1].data
                aperture = f[2].data
            time, flux = data['time'], data['flux']
            flux2 = np.asarray([imresize(abs(i) ** 2, (20, 20), mode='F') for i in flux])# if np.all(np.isfinite(i))])
            self.all_flux.append(flux2)

        self.all_flux = np.concatenate(self.all_flux)
        self.pixels.setImage(self.all_flux)

    def updateRegionChanged(self):
        self.region.setZValue(10)
        minX, maxX = self.region.getRegion()
        self.spectrum.setXRange(minX, maxX, padding=0)    

    def updateRange(self, window, viewRange):
        rgn = viewRange[0]
        self.region.setRegion(rgn)

    def setupRegion(self):
        self.region = pg.LinearRegionItem()
        self.region.setZValue(10)
        self.light_curve.addItem(self.region, ignoreBounds=True)
        self.light_curve.setAutoVisible(y=True)
        self.region.sigRegionChanged.connect(self.updateRegionChanged)
        self.spectrum.sigRangeChanged.connect(self.updateRange)
        self.region.setRegion([0., 90.])

    def setupCrosshair(self):
        region = pg.LinearRegionItem()
        region.setZValue(10)
        self.spectrum.addItem(region, ignoreBounds=True)
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.spectrum.addItem(self.vLine, ignoreBounds=True)
        self.spectrum.addItem(self.hLine, ignoreBounds=True)
        self.spectrum_mouse_proxy = pg.SignalProxy(self.spectrum.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)

    def mouseMoved(self, evt):
        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        if self.spectrum.sceneBoundingRect().contains(pos):
            mousePoint = self.spectrum.getViewBox().mapSceneToView(pos)
            index = int(mousePoint.x())
            if index > 0 and index < len(self.all_flux):
                self.label.setText("<span style='font-size: 12pt'>x=%0.1f</span>" % (mousePoint.x(),))

            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())
            self.pixels.setCurrentIndex(bisect_left(self.all_time, mousePoint.x()))

class MainWindow(qt.QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.tabs = qt.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.closePlanet)
        self.setCentralWidget(self.tabs)

        self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()

    def newPlanet(self, *args):
        text, ok = qt.QInputDialog.getText(self, 'Choose Planet',
                                           'Enter Planet:')
        if ok:
            self.tabs.addTab(PlanetGraph(text), 'Planet ' + text)

# text, ok = qt.QInputDialog().
#         dialog.exec_()
#         self.tabs.addTab(PlanetGraph(dialog.planet.text()), 'Planet ' + text)

    def closeCurrentPlanet(self):
        self.closePlanet(self.tabs.currentIndex())

    def closePlanet(self, index):
        self.tabs.removeTab(index)

    def createActions(self):
        self.newAct = qt.QAction('&New', self,
                                 shortcut=qt.QKeySequence.New, statusTip='New Planet',
                                 triggered=self.newPlanet)

        self.closeAct = qt.QAction('&Close', self,
                                   shortcut='Ctrl-W', statusTip='Close Current Planet',
                                   triggered=self.closeCurrentPlanet)

        self.exitAct = qt.QAction('E&xit', self, shortcut='Ctrl+Q',
                                  statusTip='Exit the application', triggered=self.close)

    def createMenus(self):
        self.fileMenu = self.menuBar().addMenu('&File')
        self.fileMenu.addAction(self.newAct)
        self.fileMenu.addSeparator();
        self.fileMenu.addAction(self.exitAct)

    def createToolBars(self):
        self.fileToolBar = self.addToolBar('File')
        self.fileToolBar.addAction(self.newAct)

    def createStatusBar(self):
        self.statusBar().showMessage('Ready')


if __name__ == '__main__':
    import sys, time
    app = qt.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.showMaximized()
    sys.exit(app.exec_())
