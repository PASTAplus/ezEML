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


def short_name(filename):
	# return the filename with the user directory removed
	return filename.replace(Config.BASE_DIR, '')


def clean_csv_and_zip_files(user_dir, logger, logonly):
	# remove csv and zip files, if any, left over from earlier versions of ezEML
	try:
		os.chdir(user_dir)
		filelist = list(set(glob.glob(f'{user_dir}/*.csv') + glob.glob(f'{user_dir}/*.zip') +
							glob.glob(f'{user_dir}/*.ezeml')))
		# Iterate over the list of filepaths & remove each file.
		for fpath in filelist:
			try:
				logger.info(f'Removing misplaced file {short_name(fpath)}')
				if not logonly:
					os.remove(fpath)
			except:
				logger.error(f'Error while deleting file: {fpath}')
	except FileNotFoundError:
		pass


def remove_uploads_dir_for_package(package_name, base, user_dir, logger, logonly, age=None):
	# remove the uploads dir for this package
	uploads_dir = os.path.join(base, user_dir, 'uploads', package_name)
	if os.path.exists(uploads_dir) and os.path.isdir(uploads_dir):
		try:
			if age:
				logger.info(f'Removing expired uploads directory {short_name(uploads_dir)} ...package is {age} days old')
			else:
				logger.info(f'Removing expired uploads directory {short_name(uploads_dir)}')
			if not logonly:
				shutil.rmtree(uploads_dir)
		except FileNotFoundError as err:
			logger.error(err)
			pass


def remove_backups(json_file, user_dir, logger, logonly):
	# remove the backups for this JSON file
	backups_dir = os.path.join(user_dir, 'backups')
	try:
		os.chdir(backups_dir)
		filelist = glob.glob(f'{backups_dir}/{json_file}.*')
		# Iterate over the list of filepaths & remove each file.
		for fpath in filelist:
			if os.path.exists(os.path.join(backups_dir, fpath)):
				try:
					logger.info(f'Removing backup file {short_name(fpath)}')
					if not logonly:
						os.remove(fpath)
				except:
					logger.error(f'Error while deleting file {fpath}')
	except FileNotFoundError:
		pass


def remove_exports(package_name, exports_days, user_dir, logger, logonly, age=None):
	# remove the exports directory for a package if older than exports_days
	exports_dir = os.path.join(user_dir, 'exports', package_name)
	if os.path.exists(exports_dir) and os.path.isdir(exports_dir):
		t = os.stat(exports_dir).st_mtime
		today = datetime.datetime.today()
		filetime = today - datetime.datetime.fromtimestamp(t)
		if filetime.days > exports_days:
			try:
				if age:
					logger.info(f'Removing expired exports directory {short_name(exports_dir)} ...package is {age} days old')
				else:
					logger.info(f'Removing expired exports directory {short_name(exports_dir)}')
				if not logonly:
					shutil.rmtree(exports_dir)
			except FileNotFoundError:
				pass


def clean_zip_temp_files(days, user_dir, logger, logonly):
	# Remove zip_temp files that are more than 'days' days old
	today = datetime.datetime.today()
	zip_temp_dir = os.path.join(user_dir, 'zip_temp')
	if os.path.exists(zip_temp_dir) and os.path.isdir(zip_temp_dir):
		for file in os.listdir(zip_temp_dir):
			filepath = os.path.join(zip_temp_dir, file)
			t = os.stat(filepath).st_mtime
			filetime = today - datetime.datetime.fromtimestamp(t)
			if filetime.days > days:
				try:
					logger.info(f'Removing zip_temp file {short_name(filepath)}')
					if not logonly:
						if not os.path.isdir(filepath):
							os.remove(filepath)
						else:
							shutil.rmtree(filepath)
				except FileNotFoundError:
					pass


def clean_orphans_from_directory(user_dir, dirname, dirtype, logger, logonly):
	if os.path.exists(dirname) and os.path.isdir(dirname):
		for file in os.listdir(dirname):
			filepath = os.path.join(dirname, file)
			if os.path.isdir(filepath):
				if file.startswith('.'):
					continue
				json_file = os.path.join(user_dir, file) + '.json'
				if not os.path.exists(json_file):
					try:
						logger.info(f'Removing orphaned {dirtype} directory {short_name(filepath)}')
						if not logonly:
							shutil.rmtree(filepath)
					except FileNotFoundError:
						pass


def clean_orphaned_uploads(user_dir, logger, logonly):
	# Remove directories in the uploads directory for which there is no corresponding JSON file
	# For example, if the uploads dir has a subdir named "foo", then there must be a foo.json file in the
	#  user_dir, or else the "foo" subdir is an orphan.
	uploads_dir = os.path.join(user_dir, 'uploads')
	clean_orphans_from_directory(user_dir, uploads_dir, "uploads", logger, logonly)


def clean_orphaned_exports(user_dir, logger, logonly):
	# Remove directories in the exports directory for which there is no corresponding JSON file
	# For example, if the exports dir has a subdir named "foo", then there must be a foo.json file in the
	#  user_dir, or else the "foo" subdir is an orphan.
	exports_dir = os.path.join(user_dir, 'exports')
	clean_orphans_from_directory(user_dir, exports_dir, "exports", logger, logonly)


def clean_orphaned_xml_and_eval_files(user_dir, logger, logonly):
	# Remove xml and eval pkl files for which there is no corresponding JSON file

	json_filelist = glob.glob(f'{user_dir}/*.json')
	xml_filelist = glob.glob(f'{user_dir}/*.xml')
	eval_filelist = glob.glob(f'{user_dir}/*_eval.pkl')

	for xml_file in xml_filelist:
		json_file = xml_file[:-4] + '.json'
		if json_file not in json_filelist:
			try:
				logger.info(f'Removing orphaned xml file {short_name(xml_file)}')
				if not logonly:
					os.remove(xml_file)
			except FileNotFoundError:
				pass

	for eval_file in eval_filelist:
		json_file = eval_file[:-9] + '.json'
		if json_file not in json_filelist:
			try:
				logger.info(f'Removing orphaned eval file {short_name(eval_file)}')
				if not logonly:
					os.remove(eval_file)
			except FileNotFoundError:
				pass


@click.command()
@click.option('--days', type=int, default=f'{Config.GC_DAYS_TO_LIVE}', help=f'Remove files if JSON last-modified date greater than this number of days. Default is {Config.GC_DAYS_TO_LIVE}.')
@click.option('--base', type=str, default=f'{Config.USER_DATA_DIR}', help=f'Base directory from which to crawl the file system. Default is {Config.USER_DATA_DIR}.')
@click.option('--keep_uploads', type=bool, default=f'{Config.GC_KEEP_UPLOADS}', help=f'If True, do not remove files from the uploads directories. Default is {Config.GC_KEEP_UPLOADS}.')
@click.option('--include_exports', type=bool, default=f'{Config.GC_INCLUDE_EXPORTS}', help=f'If True, include exports directories in file system crawl. Default is {Config.GC_INCLUDE_EXPORTS}.')
@click.option('--exports_days', type=int, default=f'{Config.GC_EXPORTS_DAYS_TO_LIVE}', help=f'If including exports, remove exports older than this number of days. Default is {Config.GC_EXPORTS_DAYS_TO_LIVE}.')
@click.option('--logonly', type=bool, default=f'{Config.GC_LOG_ONLY}', help=f'If True, no files are actually deleted. For testing. Default is {Config.GC_LOG_ONLY}.')
def GC(days, base, keep_uploads, include_exports, exports_days, logonly):
	logfile = os.path.join(base, 'ezEML_GC.log')
	daiquiri.setup(level=logging.INFO, outputs=(
		daiquiri.output.Stream(sys.stdout),
		daiquiri.output.File(logfile,
							 formatter=daiquiri.formatter.ColorFormatter(
								 fmt="%(asctime)s "
									 "%(name)s -> %(message)s")), 'stdout',
	))
	logger = daiquiri.getLogger(__name__)

	logger.info(f'Start run: ---------------------------------------- days={days} base={base} keep_uploads={keep_uploads} include_exports={include_exports} logonly={logonly}')
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
			clean_csv_and_zip_files(user_dir, logger, logonly)

			# find json files that haven't been modified recently
			for file in os.listdir(user_dir):
				if not file.lower().endswith('.json'):
					continue
				if file == '__user_properties__.json':
					continue
				filepath = os.path.join(user_dir, file)
				t = os.stat(filepath).st_mtime
				filetime = today - datetime.datetime.fromtimestamp(t)
				if filetime.days > days:

					# have a JSON file modified longer ago than days
					package_name = os.path.splitext(file)[0]

					# remove the uploads dir for this package
					if not keep_uploads:
						remove_uploads_dir_for_package(package_name, base, user_dir, logger, logonly, age=filetime.days)

					# remove the backups for this JSON file
					remove_backups(file, user_dir, logger, logonly)

					if include_exports:
						# remove expired exports for this package
						remove_exports(package_name, exports_days, user_dir, logger, logonly, age=filetime.days)

			# Remove zip_temp files that are more than some number of days old
			# These should be cleaned up as we go, but just in case...
			clean_zip_temp_files(Config.GC_ZIP_TEMPS_DAYS_TO_LIVE, user_dir, logger, logonly)

			# Remove orphaned directories in the uploads directory
			clean_orphaned_uploads(user_dir, logger, logonly)

			# Remove orphaned directories in the exports directory
			clean_orphaned_exports(user_dir, logger, logonly)

			# Remove xml and eval pkl files for which there is no corresponding JSON file
			clean_orphaned_xml_and_eval_files(user_dir, logger, logonly)


if __name__ == '__main__':
	GC()
