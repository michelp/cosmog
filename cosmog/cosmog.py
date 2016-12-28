
import sys

import pywt
import kplr
import numpy as np
import pyqtgraph as pg
import pyqtgraph.console
from pyqtgraph.Qt import QtGui as qt
from scipy import signal, misc
import scipy as sp

class PlanetGraph(qt.QWidget):

    def __init__(self, name, start=0, stop=-1):
        super().__init__()
        self.setupLightCurve(name, start, stop)
        self.setupCrosshair()

    def setupLightCurve(self, planet, start=0, stop=-1):
        self.client = kplr.API()
        self.planet = self.client.planet(planet)
        self.grid = qt.QGridLayout()
        self.setLayout(self.grid)

        curves = self.planet.get_light_curves()

        self.light_curve = pg.PlotWidget(name=self.planet.kepler_name)
        self.light_curve.setDownsampling(auto=True, mode='subsample')
        self.light_curve.setClipToView(True)
        self.light_curve.showGrid(x=True, y=True)
        self.light_curve.showButtons()
        self.grid.addWidget(self.light_curve, 0, 0, 1, 3)

        region = pg.LinearRegionItem()
        region.setZValue(10)
        self.light_curve.addItem(region, ignoreBounds=True)
        self.light_curve.setAutoVisible(y=True)
        
        all_time = []
        all_data = []
        for li, lc in enumerate(curves[start:stop]):
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
            self.light_curve.enableAutoRange('y', 0.97)
            all_time.append(time[m])
            all_data.append(pdcflux[m])

        all_time = np.concatenate(all_time)
        self.all_norm = np.concatenate(all_data)
        
        axis = pg.AxisItem('left')
        #axis.setTicks([xdict])
        img_view = pg.PlotItem(axis_items=dict(left=axis))
        img_view.showAxis('left')
        img_view.enableAutoRange()
        img_box = img_view.getViewBox()
        img_box.setLimits(xMin=0, yMin=0)

        self.results = pg.ImageView(view=img_view)
        #self.results.setImage(np.log2(power.T))
        self.grid.addWidget(self.results, 1, 0, 1, 3)

        self.pixels = pg.ImageView()
        tpfs = self.planet.get_target_pixel_files()

        self.all_flux = []
        for ti, tpf in enumerate(tpfs[start:stop]):
            with tpf.open() as f:
                data = f[1].data
                aperture = f[2].data
            time, flux = data['time'], data['flux']
            flux2 = np.asarray([misc.imresize(abs(i) ** 2, (20, 20), mode='F') for i in flux])
            self.all_flux.append(flux2)

        self.all_flux = np.concatenate(self.all_flux)
        self.pixels.setImage(self.all_flux)
        self.grid.addWidget(self.pixels, 0, 3)

        self.console = pyqtgraph.console.ConsoleWidget(
            namespace=dict(
                planet=self.planet,
                np=np,
                pg=pg,
                sp=sp,
                signal=signal,
                lc=self.light_curve,
                res=self.results,
                tps=self.pixels,
            ))
        self.grid.addWidget(self.console, 1, 3)

    def setupCrosshair(self):
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.light_curve.addItem(self.vLine, ignoreBounds=True)
        self.light_curve.addItem(self.hLine, ignoreBounds=True)
        self.ligh_curve_mouse_proxy = pg.SignalProxy(self.light_curve.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)

    def mouseMoved(self, evt):
        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        if self.light_curve.sceneBoundingRect().contains(pos):
            mousePoint = self.light_curve.getViewBox().mapSceneToView(pos)
            index = int(mousePoint.x())
            if index > 0 and index < len(self.all_flux):
                #self.label.setText("<span style='font-size: 12pt'>x=%0.1f," % (mousePoint.x(),))
                pass
            self.vLine.setPos(mousePoint.x())
            self.hLine.setPos(mousePoint.y())
            self.pixels.setCurrentIndex(index * 24)

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

    def newPlanet(self):
        text, ok = qt.QInputDialog.getText(self, 'Choose Planet', 
            'Enter Planet:')
        
        if ok:
            self.tabs.addTab(PlanetGraph(text), 'Planet ' + text)

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
