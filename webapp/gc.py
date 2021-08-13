import datetime
import glob
import os


import click

@click.command()
@click.option('--days', default=30, help='Remove files older than this number of days')
@click.option('--ext', default='zip', help='Remove only files with this file extension.')
@click.option('--base', default='../user-data', help='Base directory from which to crawl the file system.')
def GC(days, ext, base):
	print(days, ext, base)
	today = datetime.datetime.today()
	os.chdir(base)

	for root, directories, files in os.walk(base, topdown=False):
		for name in files:
			t = os.stat(os.path.join(root, name))[8]
			filetime = today - datetime.datetime.fromtimestamp(t)

			if filetime.days >= days and name.endswith(f'.{ext}'):
				print(os.path.join(root, name), filetime.days)
				# os.remove(os.path.join(root, name))



if __name__ == '__main__':
	GC()

