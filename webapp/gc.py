#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import glob
import logging
import os
import shutil
import sys

import click
import daiquiri

from config import Config


@click.command()
@click.option('--days', default=30, help='Remove files if JSON last-modified date greater than this number of days')
@click.option('--base', default=f'{Config.USER_DATA_DIR}', help='Base directory from which to crawl the file system.')
@click.option('--include_exports', default=False, help='If True, include exports directories in file system crawl.')
@click.option('--logonly', default=False, help='If True, no files are actually deleted. For testing.')
def GC(days, base, include_exports, logonly):
	logfile = os.path.join(base, 'ezEML_GC.log')
	daiquiri.setup(level=logging.INFO, outputs=(
		daiquiri.output.Stream(sys.stdout),
		daiquiri.output.File(logfile,
							 formatter=daiquiri.formatter.ColorFormatter(
								 fmt="%(asctime)s "
									 "%(name)s -> %(message)s")), 'stdout',
	))
	logger = daiquiri.getLogger(__name__)

	logger.info(f'Start run: ---------------------------------------- days={days} base={base} include_exports={include_exports} logonly={logonly}')
	today = datetime.datetime.today()

	os.chdir(base)

	# get the directories
	for dir in os.listdir(base):
		if os.path.isdir(os.path.join(base, dir)):
			if dir.startswith('.'):
				continue

			# got a user directory
			user_dir = os.path.join(base, dir)

			# remove csv and zip files, if any, left over from earlier versions of ezEML
			try:
				os.chdir(user_dir)
				filelist = list(set(glob.glob(f'{user_dir}/*.csv') + glob.glob(f'{user_dir}/*.zip') +
									glob.glob(f'{user_dir}/*.ezeml')))
				# Iterate over the list of filepaths & remove each file.
				for fpath in filelist:
					try:
						logger.info(f'Removing file {fpath}')
						if not logonly:
							os.remove(fpath)
					except:
						logger.error(f'Error while deleting file: {fpath}')
			except FileNotFoundError:
				pass

			# find json files that haven't been modified recently
			for file in os.listdir(user_dir):
				if not file.lower().endswith('.json'):
					continue
				filepath = os.path.join(user_dir, file)
				t = os.stat(filepath).st_mtime
				filetime = today - datetime.datetime.fromtimestamp(t)
				if filetime.days > days:

					# have a JSON file modified longer ago than days
					package_name = os.path.splitext(file)[0]

					# remove the uploads dir for this package
					uploads_dir = os.path.join(base, user_dir, 'uploads', package_name)
					if os.path.exists(uploads_dir) and os.path.isdir(uploads_dir):
						try:
							logger.info(f'Removing directory {uploads_dir}')
							if not logonly:
								shutil.rmtree(uploads_dir)
						except FileNotFoundError as err:
							logger.error(err)
							pass

					# remove the backups for this JSON file
					backups_dir = os.path.join(user_dir, 'backups')
					try:
						os.chdir(backups_dir)
						filelist = glob.glob(f'{backups_dir}/{file}.*')
						# Iterate over the list of filepaths & remove each file.
						for fpath in filelist:
							if os.path.exists(os.path.join(backups_dir, fpath)):
								try:
									logger.info(f'Removing file {fpath}')
									if not logonly:
										os.remove(fpath)
								except:
									logger.error(f'Error while deleting file {fpath}')
					except FileNotFoundError:
						pass

					if include_exports:
						# remove the exports directory for this package
						exports_dir = os.path.join(user_dir, 'exports', package_name)
						if os.path.exists(exports_dir) and os.path.isdir(exports_dir):
							try:
								logger.info(f'Removing directory {exports_dir}')
								if not logonly:
									shutil.rmtree(exports_dir)
							except FileNotFoundError:
								pass

			# Remove zip_temp files that are more than 'days' days old
			zip_temp_dir = os.path.join(user_dir, 'zip_temp')
			if os.path.exists(zip_temp_dir) and os.path.isdir(zip_temp_dir):
				for file in os.listdir(zip_temp_dir):
					filepath = os.path.join(zip_temp_dir, file)
					t = os.stat(filepath).st_mtime
					filetime = today - datetime.datetime.fromtimestamp(t)
					if filetime.days > days:
						try:
							logger.info(f'Removing file {filepath}')
							if not logonly:
								if not os.path.isdir(filepath):
									os.remove(filepath)
								else:
									shutil.rmtree(filepath)
						except FileNotFoundError:
							pass


if __name__ == '__main__':
	GC()
