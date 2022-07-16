#!/usr/bin/env python3.9
#
import csv
import logging
import os
import pickle
import sys
import time

from datetime import datetime, date
from urllib.request import urlopen

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

from config import Config

parameters = {
  'axes.labelsize': 12,
  'axes.titlesize': 20,
  'figure.figsize': [12, 8],
  'axes.labelcolor': 'gray',
  'axes.titlecolor': 'gray',
  'font.size': 12.0,
}
plt.rcParams.update(parameters)
plt.style.use(['classic', 'seaborn-talk'])

SIDC_URL = 'https://www.sidc.be/silso/DATA/EISN/EISN_current.csv'

class SSN:
  def __init__(self, cache_file, cache_time=43200):
    self.log = logging.getLogger('SSN')
    self.data = SSN.read_cache(cache_file)

    if SSN.is_expired(cache_file, cache_time):
      self.log.info('Downloading data from SIDC')
      self.data = SSN.read_url(SIDC_URL, self.data)
      SSN.write_cache(cache_file, self.data)

  @staticmethod
  def read_url(url, current_data):
    resp = urlopen(SIDC_URL)
    if resp.status != 200:
      return current_data
    charset = resp.info().get_content_charset('utf-8')
    csvfd = csv.reader(r.decode(charset) for r in resp)
    data = current_data
    for fields in csvfd:
      data.append(SSN.convert(fields))
    # de-dup
    _data = {v[0]: v for v in data}
    return sorted(_data.values())[-90:]

  @staticmethod
  def convert(fields):
    ftmp = []
    for field in fields:
      field = field.strip()
      if str.isdecimal(field):
        ftmp.append(int(field))
      elif '.' in field:
        ftmp.append(float(field))
      else:
        ftmp.append(0)
    return (date(*ftmp[:3]), *ftmp[3:])

  @staticmethod
  def read_cache(cache_file):
    try:
      with open(cache_file, 'rb') as cfd:
        return pickle.load(cfd)
    except (FileNotFoundError, EOFError):
      return []

  @staticmethod
  def write_cache(cache_file, data):
    with open(cache_file, 'wb') as cfd:
      pickle.dump(data, cfd)

  @staticmethod
  def is_expired(cache_file, cache_time):
    now = time.time()
    try:
      filest = os.stat(cache_file)
      if now - filest.st_mtime > cache_time:
        return True
    except FileNotFoundError:
      return True
    return False

  def graph(self, filename):
    if not self.data:
      self.log.warning('No data to graph')
      return None

    x = np.array([d[0] for d in self.data])
    y = np.array([int(x[2]) for x in self.data])
    error = np.array([float(x[3]) for x in self.data])
    vdata = np.array([int(x[4]) for x in self.data])
    cdata = np.array([int(x[5]) for x in self.data])

    today = datetime.utcnow().strftime('%Y/%m/%d %H:%M')
    fig = plt.figure()
    fig.suptitle('Estimated International Sunspot Number (EISN)', fontsize=14)
    fig.text(0.01, 0.02, f'SunFluxBot By W6BSD {today}')
    axgc = plt.gca()
    axgc.plot(x, y, color="blue")
    axgc.plot(x, vdata, '^', linewidth=0, color='orange')
    axgc.plot(x, cdata, 'v', linewidth=0, color='green')
    axgc.errorbar(x, y, yerr=error, fmt='o', color='green',
                  ecolor='darkolivegreen', elinewidth=1.5, capsize=7,
                  capthick=1)
    axgc.legend(['EISN', 'Valid Data', 'Entries'], loc='upper left',
                facecolor="linen")
    loc = mdates.DayLocator(interval=3)
    axgc.xaxis.set_major_formatter(mdates.DateFormatter('%a, %b %d'))
    axgc.xaxis.set_major_locator(loc)
    axgc.set_ylim(0, y.max()*1.2)

    axgc.grid()
    axgc.margins(.01)
    fig.autofmt_xdate()
    plt.savefig(filename, transparent=False, dpi=100)
    plt.close()
    self.log.info('Graph "%s" saved', filename)
    return filename

def main():
  logging.basicConfig(
    format='%(asctime)s %(name)s:%(lineno)d %(levelname)s - %(message)s', datefmt='%H:%M:%S',
    level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO'))
  )
  config = Config()
  try:
    name = sys.argv[1]
  except IndexError:
    name = '/tmp/ssn.png'

  cache_file = config.get('ssngraph.cache_file', '/tmp/ssn.pkl')
  cache_time = config.get('ssngraph.cache_time', 43200)
  ssn = SSN(cache_file, cache_time)
  if not ssn.graph(name):
    return os.EX_DATAERR

  return os.EX_OK

if __name__ == "__main__":
  sys.exit(main())
