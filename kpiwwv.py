#!/usr/bin/env python3.9
#
import logging
import os
import sqlite3
import sys

from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

import adapters

from config import Config

plt.style.use(['classic', 'seaborn-talk'])

NB_DAYS = 7

WWV_REQUEST = "SELECT wwv.time, wwv.K FROM wwv WHERE wwv.time > ?"
WWV_CONDITIONS = "SELECT conditions FROM wwv ORDER BY time DESC LIMIT 1"

def bucket(dtm):
  return int(4 * int(dtm.hour / 4))

def get_conditions(config):
  conn = sqlite3.connect(config['showdxcc.db_name'], timeout=5,
                         detect_types=sqlite3.PARSE_DECLTYPES)
  with conn:
    curs = conn.cursor()
    result = curs.execute(WWV_CONDITIONS).fetchone()
  return result[0]

def get_wwv(config, days):
  data = defaultdict(list)
  start_date = datetime.utcnow() - timedelta(days=days)
  conn = sqlite3.connect(config['showdxcc.db_name'], timeout=5,
                         detect_types=sqlite3.PARSE_DECLTYPES)
  with conn:
    curs = conn.cursor()
    results = curs.execute(WWV_REQUEST, (start_date,))
    for elem in results:
      date = elem[0]
      date = date.replace(hour=bucket(date), minute=0, second=0, microsecond=0)
      data[date].append(elem[1])

  return sorted(data.items())


def graph(data, condition, filename):

  datetm = np.array([d[0] for d in data])
  kindex = np.array([round(np.max(d[1])) for d in data])

  # I should use mpl.colormaps here
  # colors #6efa7b #a7bb36 #aa7f28 #8c4d30 #582a2d
  colors = ['#6efa7b'] * len(kindex)
  for pos, val in enumerate(kindex):
    if int(val) == 5:
      colors[pos] = '#a7bb36'
    elif val == 6:
      colors[pos] = '#aa7f28'
    elif val == 7:
      colors[pos] = '#8c4d30'
    elif val >= 8:
      colors[pos] = '#582a2d'

  today = datetime.utcnow().strftime('%Y/%m/%d %H:%M UTC')
  fig = plt.figure(figsize=(12, 5))
  fig.suptitle('Platnetary K-Index', fontsize=14, fontweight='bold')
  fig.text(0.01, 0.02, f'SunFluxBot By W6BSD {today}')
  fig.text(0.15, 0.8, "Forecast: " + condition, fontsize=12, zorder=4,
           bbox=dict(boxstyle='round', linewidth=1, facecolor='linen', alpha=1, pad=.8))

  axgc = plt.gca()
  axgc.tick_params(labelsize=10)
  axgc.bar(datetm, kindex, width=0.14, linewidth=0.75, zorder=2, color=colors)
  axgc.axhline(y=4, linewidth=1, zorder=1.5, color='red', linestyle="dashed")

  loc = mdates.DayLocator(interval=1)
  axgc.xaxis.set_major_formatter(mdates.DateFormatter('%a, %b %d UTC'))
  axgc.xaxis.set_major_locator(loc)
  axgc.xaxis.set_minor_locator(mdates.DayLocator())

  axgc.set_ylim(0, 9)
  axgc.set_ylabel('K-Index')
  axgc.grid(color="gray", linestyle="dotted", linewidth=.5)
  axgc.margins(.01)

  fig.autofmt_xdate(rotation=10, ha="center")
  plt.savefig(filename, transparent=False, dpi=100)
  plt.close()
  return filename

def main():
  adapters.install_adapers()
  logging.basicConfig(
    format='%(asctime)s %(name)s:%(lineno)d %(levelname)s - %(message)s', datefmt='%H:%M:%S',
    level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO'))
  )
  logger = logging.getLogger('kpiwwv')
  config = Config()
  try:
    name = sys.argv[1]
  except IndexError:
    name = '/tmp/kpi.png'

  data = get_wwv(config, NB_DAYS)
  condition = get_conditions(config)
  if data:
    graph(data, condition, name)
    logger.info('Graph "%s" saved', name)
  else:
    logger.warning('No data collected')


if __name__ == "__main__":
  sys.exit(main())
