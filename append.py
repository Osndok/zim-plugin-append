# -*- coding: utf-8 -*-
#
# append.py - A plugin to allow any unix-like application to create entries in the Zim wiki.
#
# Copyright 2016 - Robert Hailey <zim@osndok.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

defaultNotebook='Primary'

# ----------------------

# If you tend to make log entries past midnight, this is the number of hours past midnight that
# will be considered "the same day" (for purposes of selecting the journal page). To be most
# effective, it should be the time that you are "most surely asleep". Small for early risers, larger
# for night-owls. For example, a value of '4' would imply that the new day/page starts at '4am'.
hours_past_midnight=4

# ----------------------

import gtk

import re

import os.path

import pprint

from datetime import datetime, timedelta
from datetime import date as dateclass
from dateutil.parser import parse
from time import strftime

from zim.plugins import PluginClass, WindowExtension, extends
from zim.command import Command
from zim.actions import action
from zim.config import data_file, ConfigManager
from zim.notebook import Notebook, PageNameError, Path, NotebookInfo, \
	resolve_notebook, build_notebook
from zim.ipc import start_server_if_not_running, ServerProxy
from zim.gui.widgets import Dialog, ScrolledTextView, IconButton, \
	InputForm, gtk_window_set_default_icon, QuestionDialog
from zim.gui.clipboard import Clipboard, SelectionClipboard
from zim.gui.notebookdialog import NotebookComboBox
from zim.templates import get_template

import logging

logger = logging.getLogger('zim.plugins.append')


usagehelp = '''\
usage: zim --plugin append [OPTIONS]

Options:
'''

commandLineOptions = (
	('early'     , '0', 'Apply the text to the *VERY* start of the page (before the header).'),
	('prefix'    , '1', 'Apply the text to the beginning of the page (rather than the end)'),
	('attach='   , 'a', 'Even absent some text to append, attach this file to the page.'),
	('create'    , 'c', 'Only create a new page, do not append to an existing one.'),
	('clipboard' , 'C', 'Use the system clipboard as a source of text for this page'),
	('directory=', 'd', 'Even absent some text to append, attach every file in the given directory to the page.'),
	('exists'    , 'e', 'Only add to a pre-existing page, do not create one'),
	('file='     , 'f', 'Use the contents of the given file as the source of text to apply to the page (can be repeated).'),
	('help'      , '?', 'Print this help text and exit.'),
	('header='   , 'h', 'Seek and append-to the specified header (creating it if need be)'),
	('journal'   , 'j', 'Use todays journal page as a target'),
	('date='     , 'k', 'Use a different days journal page as a target (specified as "YYYY-mm-dd")'),
	('literal='  , 'l', 'Use the given string (passed as a parameter) as the text to apply to the page.'),
	('notebook=' , 'N', 'Select the notebook that the page is in'),
	('oldline'   , 'n', 'Dont add newlines that (ordinarily) would make the incoming text well-spaced with the current page content'),
	('page='     , 'p', 'The full page name that the text (and/or files) should be applied to'),
	('quote'     , 'q', 'Wrap the appended text in a big block-quote (or similar)'),
	('raise'     , 'r', 'Request that Zim be brought forward to the users attention (implies "show")'),
	('show'      , 's', 'Navigate Zim to the specified page (but the window may still be buried)'),
	('time'      , 't', 'Include the current time (if today\'s journal page), or the full date and time (otherwise) before the entry'),
	('usage'     , '?', 'Print this help text and exit.'),
)

multipleUseOptions=(
	'literal=',
	'file=',
	'directory=',
)

for option in commandLineOptions:
	if option[0].endswith('='):
		usagehelp += "\t--{0}<arg>,\t-{1}\t{2}\n".format(option[0], option[1], option[2])
	else:
		usagehelp += "\t--{0},\t-{1}\t{2}\n".format(option[0], option[1], option[2])

if False:
	print usagehelp
	exit

class AppendPluginCommand(Command):

	options=commandLineOptions

	def parse_options(self, *args):

		for arg in multipleUseOptions:
			self.opts[arg] = [] # allow list

		Command.parse_options(self, *args)

	def get_text(self):
		if 'input' in self.opts:
			if self.opts['input'] == 'stdin':
				import sys
				text = sys.stdin.read()
			elif self.opts['input'] == 'clipboard':
				text = \
					SelectionClipboard.get_text() \
					or Clipboard.get_text()
			else:
				raise AssertionError, 'Unknown input type: %s' % self.opts['input']
		else:
			text = self.opts.get('text')

		if text and 'encoding' in self.opts:
			if self.opts['encoding'] == 'base64':
				import base64
				text = base64.b64decode(text)
			elif self.opts['encoding'] == 'url':
				from zim.parsing import url_decode, URL_ENCODE_DATA
				text = url_decode(text, mode=URL_ENCODE_DATA)
			else:
				raise AssertionError, 'Unknown encoding: %s' % self.opts['encoding']

		if text and not isinstance(text, unicode):
			text = text.decode('utf-8')

		return text

	def run(self):
		if not self.opts or self.opts.get('help'):
			print usagehelp
		else:
			_raise = 'raise' in self.opts
			_show  = 'show'  in self.opts

			if 'notebook' in self.opts:
				notebookInfo = resolve_notebook(self.opts['notebook'])
			else:
				notebookInfo = resolve_notebook(defaultNotebook)

			print 'NotebookInfo=', notebookInfo

			# The notion of 'today' might extend into the wee hours of the morning.
			offset_time=datetime.today()-timedelta(hours=hours_past_midnight)
			todaysJournal = offset_time.strftime(':Journal:%Y:%m:%d')

			if 'page' in self.opts:
				pagename = self.opts['page']
			elif 'journal' in self.opts:
				pagename = todaysJournal;
			elif 'date' in self.opts:
				pagename = parse(self.opts['date']).strftime(':Journal:%Y:%m:%d');
			else:
				raise Exception, 'you must somehow identify a page to modify'

			print 'Pagename=', pagename

			start_server_if_not_running()
			server = ServerProxy();

			print 'Server=', server
			pprint.pprint(server.list_objects())

			# Misnomer? get_notebook returns a proxy to the main ui/gui class that is responsible for the given notebook.
			# That is to say, there is only one notebook per window.
			ui=server.get_notebook(notebookInfo, _raise or _show)
			print 'UI=', ui
			print 'Notebook?=', ui.notebook

			#dnw: page=ui.notebook.get_page(path);
			#print 'Page=', page

			quoting=('quote' in self.opts)

			text=''

			if 'literal' in self.opts:
				text += self.opts['literal']

			if 'time' in self.opts:
				if pagename==todaysJournal:
					# It's log-like... all the same day... so don't include the full date...
					text = strftime('%I:%M%P - ') + text
				else:
					text = strftime('%Y-%m-%d @ %I:%M%P - ') + text

			if 'file' in self.opts:
				if not quoting:
					text += '\n{0}:\n'.format(self.opts['file'])
				text += open(self.opts['file']).read()

			if 'clipboard' in self.opts:
				text += SelectionClipboard.get_text() or Clipboard.get_text()

			#if not 'oldline' in self.opts:
			#	text = '\n{0}\n'.format(text)

			if text and quoting:
				text="'''\n{0}\n'''".format(text)

			didSomething=False

			if text:
				# BUG: the journal template is not used for new pages...
				if self.pageExists(ui, notebookInfo, pagename):
					print 'Page exists...'

					if 'create' in self.opts:
						raise Exception, 'Page already exists: '+pagename

					ui.append_text_to_page(pagename, text);
				elif self.likelyHasChildPages(ui, notebookInfo, pagename):
					print 'Page dne, but has children... yuck...'
					# The new_page_from_text function would create enumerated side-pages...
					# so we can't use the template when creating a new page... :-(
					text = (
						"====== " + pagename + " ======\n"
						"https://github.com/Osndok/zim-plugin-append/issues/1\n\n"
						+text
					)
					ui.append_text_to_page(pagename, text);
				else:
					print 'Page does not exist'

					if 'exists' in self.opts:
						raise Exception, 'Page does not exist: '+pagename

					ui.new_page_from_text('\n'+text, name=pagename, use_template=True)

				didSomething=True

			if 'directory' in self.opts:
				ui.import_attachments(path, self.opts['directory'])
				didSomething=True

			if 'attach' in self.opts:
				ui.do_attach_file(path, self.opts['attach'])

			if _raise or _show:
				ui.present(pagename)
				didSomething=True

	def pageExists(self, ui, notebookInfo, pagename):
		#dnw: path=ui.notebook.resolve_path(pagename);
		directory=notebookInfo.uri.replace('file://', '')
		print 'Directory=', directory

		relative=Path(pagename).name.replace(':','/')+".txt"
		print 'Relative=', relative

		fullPath='{0}/{1}'.format(directory, relative)
		print 'Path=', fullPath

		return os.path.isfile(fullPath)

	def likelyHasChildPages(self, ui, notebookInfo, pagename):
		#dnw: path=ui.notebook.resolve_path(pagename);
		directory=notebookInfo.uri.replace('file://', '')
		print 'Directory=', directory

		relative=Path(pagename).name.replace(':','/')
		print 'Relative=', relative

		fullPath='{0}/{1}'.format(directory, relative)
		print 'Path=', fullPath

		return os.path.isdir(fullPath)

class AppendPlugin(PluginClass):

	plugin_info = {
		'name': _('Append'), # T: plugin name
		'description': _('''\
Intended to greatly enhance the utility of Zim by allowing for many forms of easier
input from the command line. It is not intended to be used from the GUI, does not
need to be enabled to be used, nor should it have any effect if it is actually enabled.

This is partly derived from core plugins shipped with zim.
'''), # T: plugin description
		'author': 'Robert Hailey',
		'help': 'Plugins:Append',
	}

	#~ plugin_preferences = (
		# key, type, label, default
	#~ )

