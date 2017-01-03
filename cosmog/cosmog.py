import sys
from bisect import bisect_left
import time

import pywt
import kplr
import astropy
import astropy.units as u
from astropy.stats import LombScargle
import numpy as np
import pyqtgraph as pg
import pyqtgraph.console
from pyqtgraph.Qt import QtGui as qt
from PyQt5.QtCore import Qt
from scipy import signal
from scipy.misc import imresize
import scipy as sp

class WorkerSignals(pg.QtCore.QObject):
    curve_result = pg.QtCore.Signal(object, object, object, object, int)
    tpf_result = pg.QtCore.Signal(object, object, object, object, int)

    
class LightCurveLoader(pg.QtCore.QRunnable):

    def __init__(self, index, curve):
        super().__init__()
        self.index = index
        self.curve = curve
        self.signals = WorkerSignals()

    def run(self):
        with self.curve.open() as f:
            data = f[1].data
        time = data['time']
        sapflux = data['sap_flux']
        pdcflux = data['pdcsap_flux']
        qual = data['sap_quality']
        bkg = data['sap_bkg']

        m = np.isfinite(time) * np.isfinite(pdcflux)
        mu = np.median(pdcflux[m])
        norm = (pdcflux[m] / mu - 1) * 1e6

        self.signals.curve_result.emit(time, m, norm, bkg, self.index)

            
class PlanetGraph(qt.QWidget):

    def __init__(self, planet, start=0, stop=-1):
        super().__init__()
        self.setupPool()
        self.setupModel(planet, start, stop)
        self.setupGrid()
        self.setupLightCurve()
        self.setupTargetPixels()
        self.setupZoomPlot()
        self.loadLightCurves()
        self.loadTargetPixels()
        self.setupRegion()
        self.setupCrosshair()
        self.setupPeriodogram()

    def setupPool(self):
        self.pool = pg.QtCore.QThreadPool()
        self.pool.setMaxThreadCount(100)

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
        #self.light_curve.setDownsampling(auto=True)
        self.light_curve.setClipToView(True)
        self.light_curve.showGrid(x=True, y=True)
        self.light_curve.showButtons()
        self.light_curve.setAutoVisible(y=True)
        self.light_curve.enableAutoRange('y', 0.97)
        self.grid.addWidget(self.light_curve, 0, 0, 1, 3)

    def setupZoomPlot(self):
        self.zoom_curve = pg.PlotWidget(name=self.planet.kepler_name)
        #self.zoom_curve.setDownsampling(auto=True)
        self.zoom_curve.showGrid(x=True, y=True)
        self.zoom_curve.showButtons()
        self.grid.addWidget(self.zoom_curve, 1, 0, 1, 3)

    def setupTargetPixels(self):
        self.pixels = pg.ImageView()
        self.grid.addWidget(self.pixels, 1, 4)

    def setupRegion(self):
        self.region = pg.LinearRegionItem()
        self.region.setZValue(10)
        self.light_curve.addItem(self.region, ignoreBounds=True)
        self.light_curve.setAutoVisible(y=True)
        self.region.sigRegionChanged.connect(self.updateRegionChanged)
        self.zoom_curve.sigRangeChanged.connect(self.updateRange)
        self.region.setRegion([90., 180.])
        self.last_pgram_update = time.time()

    def setupCrosshair(self):
        self.last_tpf_update = time.time()
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.zoom_curve.addItem(self.vLine, ignoreBounds=True)
        self.zoom_curve.addItem(self.hLine, ignoreBounds=True)
        self.zoom_curve_mouse_proxy = pg.SignalProxy(self.zoom_curve.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)

    def mouseMoved(self, evt):
        pos = evt[0]
        if self.zoom_curve.sceneBoundingRect().contains(pos):
            mousePoint = self.zoom_curve.getViewBox().mapSceneToView(pos)
            index = int(mousePoint.x())
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())
            self.pixels.setCurrentIndex(bisect_left(self.all_time, mousePoint.x()))

    def setupPeriodogram(self):
        self.pgram = pg.PlotWidget(name='Periodogram')
        #self.grid.addWidget(self.pgram, 0, 4)

    def loadLightCurves(self):
        self.all_time = None
        self.all_data = None
        for li, lc in enumerate(self.curve_data[self.start:self.stop]):
            t = LightCurveLoader(li, lc)
            t.signals.curve_result.connect(self.plotLightCurve)
            self.pool.start(t)

    def plotLightCurve(self, time, m, norm, bkg, li):
        self.light_curve.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=pg.mkBrush(li))
        self.light_curve.plot(time, bkg, pen=pg.mkPen('y'))
        self.zoom_curve.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=pg.mkBrush(li))
        
        if self.all_time is None:
            self.all_time = time[m]
        else:
            self.all_time = np.append(self.all_time, time[m], axis=0)
            
        if self.all_data is None:
            self.all_data = norm
        else:
            self.all_data = np.append(self.all_data, norm, axis=0)
            
    def loadTargetPixels(self):
        self.all_flux = []
        for ti, tpf in enumerate(self.tpfs[self.start:self.stop]):
            with tpf.open() as f:
                data = f[1].data
                aperture = f[2].data
            time, flux = data['time'], data['flux']
            flux2 = np.asarray([imresize(abs(i) ** 2, (20, 20), mode='F') for i in flux])# if np.all(np.isfinite(i))])
            self.all_flux.append(flux2)

        all_flux = np.concatenate(self.all_flux)
        self.pixels.setImage(all_flux)

    def updateRegionChanged(self):
        self.region.setZValue(10)
        minX, maxX = self.region.getRegion()
        self.zoom_curve.setXRange(minX, maxX, padding=0)
        # if time.time() - self.last_pgram_update < 1:
        #     return
        # self.last_pgram_update = time.time()
        
        # span = self.all_time[minX:maxX]
        # data = self.all_norm[minX:maxX]
        # t_days =  span * u.day
        # freq, power = LombScargle(t_days, data).autopower()
        # self.pgram.clear()
        # self.pgram.plot(freq, power)

    def updateRange(self, window, viewRange):
        rgn = viewRange[0]
        self.region.setRegion(rgn)


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
        self.planets = []
        console = pyqtgraph.console.ConsoleWidget(
            namespace=dict(
                self=self,
                planets=self.planets,
                pg=pg,
                qt=qt,
                np=np,
                signal=signal,
                pywt=pywt,
                kplr=kplr
            ))
        self.tabs.addTab(console, 'Console')

    def newPlanet(self, *args):
        text, ok = qt.QInputDialog.getText(
            self,
            'Choose Planet',
            'Enter Planet:')
        if ok:
            planet = PlanetGraph(text)
            self.planets.append(planet)
            self.tabs.addTab(planet, 'Planet ' + text)

    def closeCurrentPlanet(self):
        self.closePlanet(self.tabs.currentIndex())

    def closePlanet(self, index):
        if self.planets:
            self.planets.pop(index) # don't pop the console
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


if __name__ == '__main__':
    import sys, time
    app = qt.QApplication(sys.argv)
    mainWin = MainWindow()
    mainWin.showMaximized()
    sys.exit(app.exec_())
