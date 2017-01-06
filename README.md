
![Screenshot](/screenshot2.png?raw=true "Screenshot 2 of Cosmog")

# cosmog

Visualizing[Kepler](https://en.wikipedia.org/wiki/Kepler_(spacecraft)) exoplanet
data with pyqtgraph.  This is a work in progress.

End goal is to provide something interactive and informative for
Kepler data, similar to the Exoplanet Archive but with a more
interactive UI for zooming, browsing, and exploring.

Planets are shown on tabs, there is also a Python console tab with
common python libraries imported to work on matrix/astro data.

The upper left box shows all lightcurves for the planet, the lower
left box is the zoomed in transparent blue region on the upper left
box.  The upper right box is a Lomb Scargle periodogram of the blue
region.  Scrolling through the lower left zoomed in light curve, will
show the target pixel file for the (nearest) data point at that point
in time.

This requires a pretty beefy machine, a quad-core i7 with 16GB of ram
still chugs pretty hard on a single star with a lot of light curves.
My chromebook can't render more than a dozen or so light curves at once.

TODO:

    - Better inputs to control how many curves, from which quarters,
      etc.

    - All the labels.

    - Background rendering for a lot of the plot data.

    - Subsampling?  pyqtgraph's doesn't seem to help.


![Screenshot](/screenshot.png?raw=true "Screenshot of Cosmog")
