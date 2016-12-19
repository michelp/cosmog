import sys
import readline
from random import sample, choice
import numpy as np
import pywt
from pyqtgraph.Qt import QtGui
import pyqtgraph as pg
import kplr


tab_names = ['one']

# Kepler 260 b for Lacey

def main():
    app = QtGui.QApplication(sys.argv)
    tabs = QtGui.QTabWidget()
    client = kplr.API()
    planet = client.planet(raw_input('name: '))
    red = pg.mkBrush('r')
    blue = pg.mkBrush('b')

    for tab in tab_names:
        
        scroller = QtGui.QScrollArea()
        vb = pg.GraphicsWindow()
        vb.setMinimumHeight(1080)
        vb.setMinimumWidth(1920)
        scroller.setWidget(vb)

        curves = planet.get_light_curves()
        print len(curves), " curves found."
        start = input("start: ")
        stop = input("stop: ")
        
        ax = vb.addPlot(title=planet.kepler_name)
        for li, lc in enumerate(curves[start:stop]):
            with lc.open() as f:
                data = f[1].data
            print '!'
            time = data['time']
            sapflux = data['sap_flux']
            pdcflux = data['pdcsap_flux']
            qual = data['sap_quality']
            bkg = data['sap_bkg']

            brush = pg.mkBrush(li)
            brush2 = pg.mkBrush(li + 2)

            m = np.isfinite(time) * np.isfinite(pdcflux)
            m1 = m * (qual == 0)
            mu = np.median(pdcflux[m1])
            f1 = (pdcflux[m1] / mu - 1) * 1e6
            ax.plot(time[m1], f1, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=brush)

            # m2 = m * (qual != 0)
            # mu2 = np.median(pdcflux[m2])
            # f2 = (pdcflux[m2] / mu2 - 1) * 1e6
            # ax.plot(time[m2], f2, pen=None, symbol='+', symbolPen=None, symbolSize=10, symbolBrush=brush2)
            ax.plot(time, bkg, pen=pg.mkPen('y'))

        # wavelet = 'cmor'
        # scales = np.arange(1,128)
        # [cfs,frequencies] = pywt.cwt(sst, scales, wavelet)
        # power = (abs(cfs)) ** 2

        # period = 1. / frequencies
        # levels = [0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8]
        # img = pg.ImageItem(data[0])
        # vb.addItem(img)
        
        
        tabs.addTab(scroller, tab)

    tabs.setWindowTitle('Cosmog')
    tabs.resize(1920, 1080)
    tabs.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
