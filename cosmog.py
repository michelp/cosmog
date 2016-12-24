import sys
import readline
from random import sample, choice
import numpy as np
import pywt
from pyqtgraph.Qt import QtGui
import pyqtgraph as pg
from pyqtgraph import opengl
import kplr
from scipy import signal


tab_names = ['one']

# Kepler 260 b for Lacey

def main():
    app = QtGui.QApplication(sys.argv)
    tabs = QtGui.QTabWidget()

    client = kplr.API()
    planet = client.planet(sys.argv[1])
    red = pg.mkBrush('r')
    blue = pg.mkBrush('b')

    for tab in tab_names:

        scroller = QtGui.QScrollArea()
        vb = pg.GraphicsWindow()
        vb.setMinimumHeight(1000)
        vb.setMinimumWidth(1920)
        scroller.setWidget(vb)

        curves = planet.get_light_curves()
        print len(curves), " curves found."
        ax = vb.addPlot(title=planet.kepler_name)
        all_data = []
        for li, lc in enumerate(curves):
            print lc.url
            with lc.open() as f:
                data = f[1].data
            #data = data[np.random.randint(data.shape[0], size=len(data)/2), :]
            time = data['time']
            sapflux = data['sap_flux']
            pdcflux = data['pdcsap_flux']
            qual = data['sap_quality']
            bkg = data['sap_bkg']
            #import ipdb; ipdb.set_trace()

            brush = pg.mkBrush(li)

            m = np.isfinite(time) * np.isfinite(pdcflux)
            mu = np.median(pdcflux[m])
            norm = (pdcflux[m] / mu - 1) * 1e6

            # corrected flux and background noise
            ax.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=brush)
            ax.plot(time, bkg, pen=pg.mkPen('y'))
            ax.enableAutoRange('y', 0.97)
            all_data.append(norm)

        all_norm = np.concatenate(all_data)
        wavelet = 'cmor'
        scales = np.arange(1,128)
        [cfs,frequencies] = pywt.cwt(all_norm, scales, wavelet)
        power = (abs(cfs)) ** 2

        period = 1. / frequencies
        levels = [0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8]
        vb.nextRow()
        iview = vb.addViewBox()
        img = pg.ImageItem()
        iview.addItem(img)
        img.setImage(power)
        tabs.addTab(scroller, tab)

    tabs.setWindowTitle('Cosmog')
    tabs.resize(1920, 1080)
    tabs.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
