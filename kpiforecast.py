#!/usr/bin/env python3.9
#
import json
import logging
import os
import pickle
import sys
import time
import urllib.request

from datetime import datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from config import Config

NOAA_URL = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index-forecast.json'

plt.style.use(['classic', 'seaborn-talk'])

class KPIForecast:
  def __init__(self, cache_file, cache_time=21600):
    self.log = logging.getLogger('KPIForecast')
    self.cachefile = cache_file
    self.data = None

    now = time.time()
    try:
      filest = os.stat(self.cachefile)
      if now - filest.st_mtime > cache_time: # 6 hours
        raise FileNotFoundError
    except FileNotFoundError:
      self.download()
      if self.data:
        self.writecache()
    finally:
      self.readcache()

  def graph(self, filename):
    if not self.data:
      self.log.warning('No data to graph')
      return None

    start_date = datetime.utcnow() - timedelta(days=3, hours=4)
    end_date = datetime.utcnow() + timedelta(days=1, hours=6)
    xdates = np.array([d[0] for d in self.data if start_date < d[0] < end_date])
    yvalues = np.array([np.average(d[1]) for d in self.data if start_date < d[0] < end_date])
    observ = [d[2] for d in self.data if start_date < d[0] < end_date]
    labels = [d[3] for d in self.data if start_date < d[0] < end_date]

    colors = ['lightgreen'] * len(observ)
    for pos, (obs, val)  in enumerate(zip(observ, yvalues)):
      if obs == 'observed':
        if int(val) == 4:
          colors[pos] = 'darkorange'
        elif int(val) > 4:
          colors[pos] = 'red'
      elif obs == "estimated":
        colors[pos] = 'lightgrey'
      elif obs == "predicted":
        colors[pos] = 'darkgrey'

    date = datetime.utcnow().strftime('%Y:%m:%d %H:%M UTC')
    plt.rc('xtick', labelsize=10)
    plt.rc('ytick', labelsize=10)
    fig = plt.figure(figsize=(12, 5))
    fig.suptitle('Planetary K-Index Predictions', fontsize=14, fontweight='bold')
    axgc = plt.gca()
    bars = axgc.bar(xdates, yvalues, width=.1, linewidth=0.75, zorder=2, color=colors)
    axgc.axhline(y=4, linewidth=1, zorder=1.5, color='red', linestyle="dashed")

    for rect, obs, label in zip(*(bars, observ, labels)):
      if not label:
        continue
      color = 'white' if obs == 'observed' else 'black'
      axgc.text(rect.get_x() + rect.get_width() / 2., .3, label, alpha=1,
                color=color, fontweight="bold", fontsize="12", ha='center')

    loc = mdates.DayLocator(interval=1)
    axgc.xaxis.set_major_formatter(mdates.DateFormatter('%a, %b %d UTC'))
    axgc.xaxis.set_major_locator(loc)
    axgc.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
    axgc.set_ylim(0, 9)

    axgc.axhspan(0, 0, facecolor='lightgrey', alpha=1, label='Estimated')
    axgc.axhspan(0, 0, facecolor='darkgrey', alpha=1, label='Predicted')
    axgc.legend(fontsize=10, loc="best", facecolor="linen", borderaxespad=1)

    axgc.grid(color="gray", linestyle="dotted", linewidth=.5)
    axgc.margins(x=.01)

    fig.autofmt_xdate(rotation=10, ha="center")

    plt.figtext(0.02, 0.02, f'SunFluxBot By W6BSD {date}')
    plt.savefig(filename, transparent=False, dpi=100)
    plt.close()
    self.log.info('Graph "%s" saved', filename)
    return filename

  def download(self):
    self.log.info('Downloading data from NOAA')
    res = urllib.request.urlopen(NOAA_URL)
    webdata = res.read()
    encoding = res.info().get_content_charset('utf-8')
    _data = json.loads(webdata.decode(encoding))
    data = []
    for elem in _data[1:]:
      date = datetime.strptime(elem[0], '%Y-%m-%d %H:%M:%S')
      data.append((date, int(elem[1]), *elem[2:]))
    self.data = sorted(data)

  def readcache(self):
    """Read data from the cache"""
    self.log.debug('Read from cache "%s"', self.cachefile)
    try:
      with open(self.cachefile, 'rb') as fd_cache:
        data = pickle.load(fd_cache)
    except (FileNotFoundError, EOFError):
      data = None
    self.data = data

  def writecache(self):
    """Write data into the cachefile"""
    self.log.debug('Write cache "%s"', self.cachefile)
    with open(self.cachefile, 'wb') as fd_cache:
      pickle.dump(self.data, fd_cache)

def main():
  logging.basicConfig(
    format='%(asctime)s %(name)s:%(lineno)d %(levelname)s - %(message)s', datefmt='%H:%M:%S',
    level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO'))
  )
  config = Config()
  try:
    name = sys.argv[1]
  except IndexError:
    name = '/tmp/kpiforecast.png'

  cache_file = config.get('kpiforecast.cache_file', '/tmp/kpiforecast.pkl')
  cache_time = config.get('kpiforecast.cache_time', 21600)
  kpi = KPIForecast(cache_file, cache_time)
  if not kpi.graph(name):
    return os.EX_DATAERR

  return os.EX_OK

if __name__ == "__main__":
  sys.exit(main())
