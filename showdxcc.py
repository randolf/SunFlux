#!/usr/bin/env python3
#
# BSD 3-Clause License
#
# Copyright (c) 2022-2023 Fred W6BSD
# All rights reserved.
#
#

import argparse
import logging
import os
import sqlite3
import sys

from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np

import adapters

from config import Config

CONTINENTS = ['AF', 'AS', 'EU', 'NA', 'OC', 'SA']
BANDS = [6, 10, 12, 15, 17, 20, 30, 40, 60, 80, 160]

class ShowDXCC:

  def __init__(self, config, zone_name, zone, date=None):
    self.config = config
    self.date = date if date else datetime.utcnow()
    self.data = []
    self.zone_name = zone_name
    try:
      self.zone = int(zone)
    except ValueError:
      self.zone = f'"{zone}"'

    try:
      self.zone_label = {'continent': 'de_cont',
                         'ituzone': 'de_ituzone',
                         'cqzone': 'de_cqzone'}[zone_name]
    except KeyError:
      raise SystemError(f'Zone {zone_name} error')

  def is_data(self):
    return np.any(self.data)

  def get_dxcc(self, delta=1):
    start_date = self.date - timedelta(hours=delta, minutes=0)
    end_date = self.date
    request = (f"SELECT band, de_cont, to_cont, COUNT(*) FROM dxspot WHERE band >= 6 "
               f"AND {self.zone_label} = {self.zone} "
               f"AND time > {start_date.timestamp()} "
               f"AND time <= {end_date.timestamp()} "
               "GROUP BY band, to_cont;")
    conn = sqlite3.connect(self.config['showdxcc.db_name'], timeout=5,
                           detect_types=sqlite3.PARSE_DECLTYPES)
    logging.debug(request)
    with conn:
      curs = conn.cursor()
      results = curs.execute(request).fetchall()

    self.data = np.zeros((len(CONTINENTS), len(BANDS)), dtype=int)
    for band, _, to_continent, count in results:
      x = CONTINENTS.index(to_continent)
      y = BANDS.index(band)
      self.data[x, y] = count

  def graph(self, filename):
    color_map = self.config.get('showdxcc.color_map', 'PRGn')
    fig, axgc = plt.subplots(figsize=(12,8), facecolor='white')

    # Show all ticks and label them with the respective list entries
    plt.xticks(np.arange(len(BANDS)), labels=BANDS, fontsize=14)
    plt.xlabel("Bands", fontsize=14)
    plt.yticks(np.arange(len(CONTINENTS)), labels=CONTINENTS, fontsize=14)
    plt.ylabel("Destination", fontsize=14)

    image = axgc.imshow(
      self.data, cmap=color_map,
      interpolation=self.config.get('showdxcc.interleave', 'gaussian')
    )
    axgc.set_aspect(aspect=1)
    axgc.tick_params(top=True, bottom=True, labeltop=True, labelbottom=True)

    cbar = axgc.figure.colorbar(image, ax=axgc, shrink=0.66, format="%5.0f")
    cbar.ax.tick_params(labelsize=10)

    # Loop over data dimensions and create text annotations.
    threshold = np.percentile(self.data, 96)
    for i in range(len(CONTINENTS)):
      for j in range(len(BANDS)):
        if self.data[i, j] < 1:
          continue
        color = 'firebrick' if self.data[i, j] > threshold else 'lime'
        axgc.text(j, i, self.data[i, j], ha="center", va="center", color=color)

    axgc.set_title(f"Band activity from {self.zone_name} = {self.zone}",
                   fontsize=16, fontweight='bold')
    fig.text(0.02, .03, 'SunFluxBot By W6BSD', fontsize=14)
    fig.text(0.65, .95, f'{self.date.strftime("%A %B %d %Y - %H:%M")}', fontsize=14)
    fig.tight_layout()
    logging.info('Save %s', filename)
    fig.savefig(filename, transparent=False, dpi=100)


def type_date(parg):
  if parg == 'now':
    date = datetime.utcnow()
    date = date.replace(second=0, microsecond=0)
    return date

  try:
    date = datetime.strptime(parg, '%Y%m%d%H%M')
  except ValueError:
    raise argparse.ArgumentTypeError from None
  return date


def create_link(filename):
  path, fname = os.path.split(filename)
  fname, ext = os.path.splitext(fname)
  latest = os.path.join(path, f'latest{ext}')
  if os.path.exists(latest):
    os.unlink(latest)
  os.link(filename, latest)
  logging.info('Link to %s created', latest)


def main():
  adapters.install_adapters()
  config = Config()

  logging.basicConfig(
    format='%(asctime)s %(name)s:%(lineno)d %(levelname)s - %(message)s', datefmt='%H:%M:%S',
    level=logging.getLevelName(os.getenv('LOG_LEVEL', 'INFO'))
  )

  parser = argparse.ArgumentParser(description="Graph dxcc trafic")
  parser.add_argument("-d", "--date", type=type_date, default='now',
                      help="Graph date [YYYYMMDDHHMM]")
  parser.add_argument("-D", "--delta", type=int, default=1,
                      help="Number of hours [default: %(default)d]")
  parser.add_argument("-L", "--no-link", action="store_false", default=True,
                      help="Update the link \"latest\"")
  z_group = parser.add_mutually_exclusive_group(required=True)
  z_group.add_argument("-c", "--continent", choices=CONTINENTS, help="Continent")
  z_group.add_argument("-I", "--ituzone", type=int, help="itu zone")
  z_group.add_argument("-C", "--cqzone", type=int, help="cq zone")
  parser.add_argument('args', nargs="*")
  opts = parser.parse_args()

  for zone_name in ('continent', 'ituzone', 'cqzone'):
    zone = getattr(opts, zone_name)
    if zone:
      zone = str(zone)
      break

  if opts.args:
    filename = opts.args[0]
  else:
    now = opts.date.strftime('%Y%m%d%H%M')
    target_root = config.get('showdxcc.target_dir', '/var/tmp/dxcc')
    if opts.continent:
      target_dir = os.path.join(target_root, opts.continent)
      os.makedirs(target_dir, exist_ok=True)
      filename = os.path.join(target_dir, f'dxcc-{opts.continent}-{now}.png')
    else:
      target_dir = os.path.join(target_root, zone_name, zone)
      os.makedirs(target_dir, exist_ok=True)
      filename = os.path.join(target_dir, f'dxcc-{zone_name}{zone}-{now}.png')


  showdxcc = ShowDXCC(config, zone_name, zone, opts.date)
  showdxcc.get_dxcc(opts.delta)
  showdxcc.graph(filename)
  if opts.no_link:
    create_link(filename)

  sys.exit(os.EX_OK)

if __name__ == "__main__":
  sys.exit(main())
