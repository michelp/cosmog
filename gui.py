#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys

import pywt
import kplr
import numpy as np
import pyqtgraph as pg
from scipy import signal, misc
from pyqtgraph.Qt import QtGui as qt


class PlanetGraph(qt.QWidget):
    
    def __init__(self):
        super().__init__()
        grid = qt.QGridLayout()
        self.setLayout(grid)

        self.client = kplr.API()
        self.planet = self.client.planet(sys.argv[1])

        win = pg.GraphicsWindow()
        grid.addWidget(win, 0, 0, 1, 3)

        curves = self.planet.get_light_curves()
        print(len(curves), " curves found.")
        start = int(sys.argv[2])
        stop = int(sys.argv[3])
        ax = win.addPlot(title=self.planet.kepler_name)
        all_time = []
        all_data = [] 
        for li, lc in enumerate(curves[start:stop]):
            with lc.open() as f:
                data = f[1].data
            #data = data[np.random.randint(data.shape[0], size=len(data)/2), :]
            time = data['time']
            sapflux = data['sap_flux']
            pdcflux = data['pdcsap_flux']
            qual = data['sap_quality']
            bkg = data['sap_bkg']

            m = np.isfinite(time) * np.isfinite(pdcflux)
            mu = np.median(pdcflux[m])
            norm = (pdcflux[m] / mu - 1) * 1e6

            # corrected flux and background noise
            ax.plot(time[m], norm, pen=None, symbol='x', symbolPen=None, symbolSize=10, symbolBrush=pg.mkBrush(li))
            ax.plot(time, bkg, pen=pg.mkPen('y'))
            ax.enableAutoRange('y', 0.97)
            all_time.append(time[m])
            all_data.append(pdcflux[m])

        all_time = np.concatenate(all_time)
        all_norm = np.concatenate(all_data)

        #import ipdb; ipdb.set_trace()

        # dt = all_time[1] - all_time[0]
        # scales = np.arange(1,64)
        # [cfs, frequencies] = pywt.cwt(all_norm, scales, wavelet, dt)
        # power = (abs(cfs)) ** 2

        # period = 1. / frequencies

        wavelet = 'db12'
        level = 9
        order = "freq"  # other option is "normal"

        wp = pywt.WaveletPacket(all_norm, wavelet, 'symmetric', maxlevel=level)
        nodes = wp.get_level(level, order=order)
        labels = [n.path for n in nodes]
        values = np.array([n.data for n in nodes], 'd')
        power = abs(values) ** 2

        xdict = dict(enumerate(map(str, labels)))

        axis = pg.AxisItem('left')
        axis.setTicks([xdict])
        img_view = pg.PlotItem(axis_items=dict(left=axis))
        img_view.showAxis('left')
        img_view.enableAutoRange()
        img_box = img_view.getViewBox()
        img_box.setLimits(xMin=0, yMin=0)
        
        img = pg.ImageView(view=img_view)
        img.setImage(np.log2(power.T))
        img_box.invertY(False)
        grid.addWidget(img, 1, 0, 1, 2)

        pixels = pg.ImageView()

        tpfs = self.planet.get_target_pixel_files()

        all_flux = []
        #import ipdb; ipdb.set_trace()
        for ti, tpf in enumerate(tpfs[start:stop]):
            with tpf.open() as f:
                data = f[1].data
                aperture = f[2].data
            time, flux = data["time"], data["flux"]
            flux2 = np.asarray([misc.imresize(abs(i) ** 2, (20, 20), mode='F') for i in flux])
            all_flux.append(flux2)

        all_flux = np.concatenate(all_flux)
        pixels.setImage(all_flux)
        grid.addWidget(pixels, 1, 2)
            
        self.setWindowTitle('Cosmog for ' + self.planet.kepler_name)
        self.showMaximized()
        
        
if __name__ == '__main__':
    
    app = qt.QApplication(sys.argv)
    ex = PlanetGraph()
    sys.exit(app.exec_())
    
