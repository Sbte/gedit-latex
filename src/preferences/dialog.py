# -*- coding: utf-8 -*-

# This file is part of the Gedit LaTeX Plugin
#
# Copyright (C) 2008 Michael Zeising
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public Licence as published by the Free Software
# Foundation; either version 2 of the Licence, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public Licence for more 
# details.
#
# You should have received a copy of the GNU General Public Licence along with
# this program; if not, write to the Free Software Foundation, Inc., 51 Franklin
# Street, Fifth Floor, Boston, MA  02110-1301, USA

"""
preferences.dialog
"""

from logging import getLogger
import gtk
from gtk import gdk

from ..base.resources import find_resource
from ..util import GladeInterface
from . import Preferences


class PreferencesColorProxy(object):
	"""
	This connects to a gtk.gdk.Color and gets/sets the value of a certain
	preference
	"""
	def __init__(self, widget, key, default_value):
		"""
		@param widget: the gtk.Widget that serves as a proxy
		@param key: the key of the preferences field to be managed
		"""
		self._widget = widget
		self._key = key
		self._preferences = Preferences()
		
		# init value
		self._widget.set_color(gdk.color_parse(self._preferences.get(key, default_value)))
		
		# listen to change
		self._widget.connect("color-set", self._on_color_set)
	
	def _on_color_set(self, color_button):
		self._preferences.set(self._key, self._color_to_hex(color_button.get_color()))
	
	def _color_to_hex(self, color):
		"""
		Convert the value of a gtk.gdk.Color widget to a hex color value
		
		@param color: gtk.gdk.Color
		"""
		
		# gtk.gdk.Color components have range 0-65535
		
		r = int((float(color.red) / 65535.0) * 255.0)
		g = int((float(color.green) / 65535.0) * 255.0)
		b = int((float(color.blue) / 65535.0) * 255.0)
		
		return "#%02x%02x%02x" % (r, g, b)


from ..tools import Tool, Job


class ConfigureToolDialog(GladeInterface):
	"""
	Wraps the dialog for setting up a Tool
	"""
	
	filename = find_resource("glade/configure_tool.glade")
	
	_dialog = None
	
	def run(self, tool):
		"""
		Runs the dialog and returns the updated Tool or None on abort
		"""
		dialog = self._get_dialog()
		
		self._tool = tool
		
		# load Tool
		self._entry_label.set_text(tool.label)
		self._entry_description.set_text(tool.description)
		
		self._store_job.clear()
		for job in tool.jobs:
			self._store_job.append([job.command_template, job.must_succeed, job.post_processor.name])
		
		self._store_extension.clear()
		for ext in tool.extensions:
			self._store_extension.append([ext])
		
		if dialog.run() == 1:
			#
			# okay clicked - update the Tool object
			#
			tool.label = self._entry_label.get_text()
			tool.description = self._entry_description.get_text()
			
			tool.jobs = []
			for row in self._store_job:
				pp_class = self._preferences.POST_PROCESSORS[row[2]]
				tool.jobs.append(Job(row[0], row[1], pp_class))
				
			tool.extensions = []
			for row in self._store_extension:
				tool.extensions.append(row[0])
				
			return tool
		else:
			return None
	
	def _get_dialog(self):
		if not self._dialog:
			# 
			# build the dialog
			#
			self._preferences = Preferences()
			
			self._dialog = self.find_widget("dialogConfigureTool")
			self._button_okay = self.find_widget("buttonOkay")
			self._labelProfileValidate = self.find_widget("labelHint")
			
			#
			# label
			#
			self._entry_label = self.find_widget("entryLabel")
			
			#
			# jobs
			#
			self._entry_new_job = self.find_widget("entryNewJob")
			self._button_add_job = self.find_widget("buttonAddJob")
			self._button_remove_job = self.find_widget("buttonRemoveJob")
			self._button_job_up = self.find_widget("buttonMoveUpJob")
			self._view_job = self.find_widget("treeviewJob")
			
			self._store_job = gtk.ListStore(str, bool, str)   # command, mustSucceed, postProcessor
			
			self._view_job.set_model(self._store_job)
			
			mustSucceedRenderer = gtk.CellRendererToggle()
			mustSucceedRenderer.connect("toggled", self._on_must_succeed_toggled)
			
			commandRenderer = gtk.CellRendererText()
			commandRenderer.connect("edited", self._on_job_command_edited)

			self._store_pp = gtk.ListStore(str)
			for p in self._preferences.POST_PROCESSORS.iterkeys():
				self._store_pp.append([p])
			
			ppRenderer = gtk.CellRendererCombo()
			ppRenderer.set_property("editable", True)
			ppRenderer.set_property("model", self._store_pp)
			ppRenderer.set_property("text_column", 0)
			ppRenderer.set_property("has_entry", False)
			
			ppRenderer.connect("edited", self._on_job_pp_edited)
			
			self._view_job.insert_column_with_attributes(-1, "Command", commandRenderer, text=0, editable=True)
			self._view_job.insert_column_with_attributes(-1, "Must Succeed", mustSucceedRenderer, active=1)
			self._view_job.insert_column_with_attributes(-1, "Post-Processor", ppRenderer, text=2)
			
			#
			# description
			#
			self._entry_description = self.find_widget("entryDescription")
			
			#
			# extensions
			#
			self._entry_new_extension = self.find_widget("entryNewExtension")
			
			self._store_extension = gtk.ListStore(str)
			
			self._view_extension = self.find_widget("treeviewExtension")
			self._view_extension.set_model(self._store_extension)
			self._view_extension.insert_column_with_attributes(-1, "", gtk.CellRendererText(), text=0)
			self._view_extension.set_headers_visible(False)
			
			self._button_add_extension = self.find_widget("buttonAddExtension")
			self._button_remove_extension = self.find_widget("buttonRemoveExtension")
			
			self.connect_signals({ "on_entryNewJob_changed" : self._on_new_job_changed,
								   "on_entryNewExtension_changed" : self._on_new_extension_changed,
								   "on_buttonAddJob_clicked" : self._on_add_job_clicked,
								   "on_buttonRemoveJob_clicked" : self._on_remove_job_clicked,
								   "on_treeviewJob_cursor_changed" : self._on_job_cursor_changed,
								   "on_treeviewExtension_cursor_changed" : self._on_extension_cursor_changed,
								   "on_buttonAbort_clicked" : self._on_abort_clicked,
								   "on_buttonOkay_clicked" : self._on_okay_clicked,
								   "on_buttonRemoveExtension_clicked" : self._on_remove_extension_clicked,
								   "on_buttonAddExtension_clicked" : self._on_add_extension_clicked,
								   "on_buttonMoveUpJob_clicked" : self._on_move_up_job_clicked })
		
		return self._dialog
	
	def _on_move_up_job_clicked(self, button):
		store, iter = self._view_job.get_selection().get_selected()
		
		s = store.get_string_from_iter(iter)		# e.g. "3"
		
		store.swap(iter)
	
	def _on_add_extension_clicked(self, button):
		extension = self._entry_new_extension.get_text()
		self._store_extension.append([extension])
	
	def _on_remove_extension_clicked(self, button):
		store, it = self._view_extension.get_selection().get_selected()
		store.remove(it)
	
	def _on_job_command_edited(self, renderer, path, text):
		"""
		The command template has been edited
		"""
		self._store_job.set(self._store_job.get_iter_from_string(path), 0, text)
	
	def _on_job_pp_edited(self, renderer, path, text):
		"""
		Another post processor has been selected
		"""
		self._store_job.set(self._store_job.get_iter_from_string(path), 2, text)
	
	def _on_must_succeed_toggled(self, renderer, path):
		"""
		The 'must succeed' flag has been toggled
		"""
		value = self._store_job.get(self._store_job.get_iter_from_string(path), 1)[0]
		self._store_job.set(self._store_job.get_iter_from_string(path), 1, not value)
	
	def _on_add_job_clicked(self, button):
		"""
		Add a new job
		"""
		command = self._entry_new_job.get_text()
		self._store_job.append([command, True, "GenericPostProcessor"])
	
	def _on_remove_job_clicked(self, button):
		store, it = self._view_job.get_selection().get_selected()
		store.remove(it)
	
	def _on_new_job_changed(self, widget):
		"""
		The entry for a new command template has changed
		"""
		self._button_add_job.set_sensitive(len(self._entry_new_job.get_text()) > 0)
	
	def _on_new_extension_changed(self, widget):
		self._button_add_extension.set_sensitive(len(self._entry_new_extension.get_text()) > 0)
	
	def _on_job_cursor_changed(self, tree_view):
		store, iter = tree_view.get_selection().get_selected()
		if not iter: 
			return
		self._button_remove_job.set_sensitive(True)
		
		first_row_selected = (store.get_string_from_iter(iter) == "0")
		self._button_job_up.set_sensitive(not first_row_selected)
	
	def _on_extension_cursor_changed(self, tree_view):
		store, it = tree_view.get_selection().get_selected()
		if not it: 
			return
		self._button_remove_extension.set_sensitive(True)
	
	def _on_abort_clicked(self, button):
		self._dialog.hide()
	
	def _on_okay_clicked(self, button):
		self._dialog.hide()
	
	def _validate_tool(self):
		"""
		Validate the dialog contents
		"""
		errors = []
		
		if len(self._store_job) == 0:
			errors.append("You have not specified any jobs.")
		
		if len(errors):
			self._buttonApply.set_sensitive(False)
		else:
			self._buttonApply.set_sensitive(True)
		
		if len(errors) == 1:
			self._labelProfileValidate.set_markup(errors[0])
		elif len(errors) > 1:
			self._labelProfileValidate.set_markup("\n".join([" * %s" % e for e in errors]))
		else:
			self._labelProfileValidate.set_markup("Remember to run all commands in batch mode (e.g. append <tt>-interaction batchmode</tt> to <tt>latex</tt>)")
	
	

class PreferencesDialog(GladeInterface):
	"""
	This controls the configure dialog
	"""
	
	_log = getLogger("PreferencesWizard")
	
	filename = find_resource("glade/configure.glade")
	_dialog = None
	
	@property
	def dialog(self):
		if not self._dialog:
			self._preferences = Preferences()
			
			self._dialog = self.find_widget("dialogConfigure")
			
			self._buttonApply = self.find_widget("buttonApply")
			
			#
			# snippets
			#
			self._store_snippets = gtk.ListStore(bool, str, object) 	# active, name, Template instance
			
#			for template in self._preferences.templates:
#				self._store_snippets.append([True, template.name, template])
				
			self._view_snippets = self.find_widget("treeviewTemplates")
			self._view_snippets.set_model(self._store_snippets)
			self._view_snippets.insert_column_with_attributes(-1, "Active", gtk.CellRendererToggle(), active=0)
			self._view_snippets.insert_column_with_attributes(-1, "Name", gtk.CellRendererText(), text=1)
			
			self._entry_snippet = self.find_widget("textviewTemplate")
			
			#
			# recent bibliographies
			#
			self._storeBibs = gtk.ListStore(str)
			
#			for bib in self._preferences.bibliographies:
#				self._storeBibs.append([bib.filename])
				
			self._viewBibs = self.find_widget("treeviewBibs")
			self._viewBibs.set_model(self._storeBibs)
			self._viewBibs.insert_column_with_attributes(-1, "Filename", gtk.CellRendererText(), text=0)
			
			#
			# tools
			#
			
			# grab widgets
			self._entryProfileName = self.find_widget("entryProfileName")
			
			#self._buttonProfileSave = self.find_widget("buttonProfileSave")
			#self._entryViewCommand = self.find_widget("entryViewCommand")
			#self._entryOutputFile = self.find_widget("entryOutputFile")
			
			# tools
			
			self._store_tool = gtk.ListStore(str, str, object)     # label markup, extensions, Tool instance
			
			self.__load_tools()
				
			self._view_tool = self.find_widget("treeviewProfiles")
			self._view_tool.set_model(self._store_tool)
			self._view_tool.insert_column_with_attributes(-1, "Label", gtk.CellRendererText(), markup=0)
			self._view_tool.insert_column_with_attributes(-1, "File Extensions", gtk.CellRendererText(), text=1)
			
			
			
			#
			# spell check
			#
			try:
				# the import may fail if enchant is not installed
				from spellcheck import EnchantFacade
				
				
				self._storeLanguages = gtk.ListStore(str)
				
				enchant = EnchantFacade()
				for l in enchant.getLanguages():
					self._storeLanguages.append([l])
				
				self._comboLanguages = self.find_widget("comboLanguages")
				self._comboLanguages.set_model(self._storeLanguages)
				cell = gtk.CellRendererText()
				self._comboLanguages.pack_start(cell, True)
				self._comboLanguages.add_attribute(cell, "text", 0)
				self._comboLanguages.set_active(0)
			except ImportError:
				
				self._log.error("Enchant library could not be imported. Spell checking will be disabled.")
				# TODO: show warning 
				
				pass
			
			#
			# colors
			#
			self._color_proxies = [ PreferencesColorProxy(self.find_widget("colorLight"), "LightForeground", "#957d47"),
									PreferencesColorProxy(self.find_widget("colorSpelling"), "SpellingBackgroundColor", "#ffeccf"),
									PreferencesColorProxy(self.find_widget("colorWarning"), "WarningBackgroundColor", "#ffffcf"),
									PreferencesColorProxy(self.find_widget("colorError"), "ErrorBackgroundColor", "#ffdddd") ]
			
			#
			# signals
			#
			self.connect_signals({ "on_buttonApply_clicked" : self._on_apply_clicked,
								   "on_buttonAbort_clicked" : self._on_abort_clicked,
								   "on_treeviewTemplates_cursor_changed" : self._on_snippet_changed,
								   "on_treeviewProfiles_cursor_changed" : self._on_tool_changed,
								   #"on_buttonProfileSave_clicked" : self._on_save_tool_clicked,
								   "on_buttonNewTemplate_clicked" : self._on_new_snippet_clicked,
								   "on_buttonSaveTemplate_clicked" : self._on_save_snippet_clicked,
								   "on_buttonNewProfile_clicked" : self._on_new_tool_clicked,
								   "on_buttonMoveDownProfile_clicked" : self._on_tool_down_clicked,
								   "on_buttonConfigureTool_clicked" : self._on_configure_tool_clicked,
								   "on_buttonDeleteTool_clicked" : self._on_delete_tool_clicked })
			
		return self._dialog
	
	def __load_tools(self):
		self._store_tool.clear()
		for tool in self._preferences.tools:
			self._store_tool.append(["<b>%s</b>" % tool.label, ", ".join(tool.extensions), tool])
	
	def _on_configure_tool_clicked(self, button):
		store, it = self._view_tool.get_selection().get_selected()
		tool = store.get_value(it, 2)
		
		dialog = ConfigureToolDialog()
		
		if not dialog.run(tool) is None:
			self._preferences.save_or_update_tool(tool)
	
	def _on_delete_tool_clicked(self, button):
		store, it = self._view_tool.get_selection().get_selected()
		tool = store.get_value(it, 2)
		
		self._preferences.delete_tool(tool)
		
		# TODO: better: remove from store
		
		self.__load_tools()
	
	def _on_tool_down_clicked(self, button):
		store, it = self._view_tool.get_selection().get_selected()
		profile = store.get_value(it, 1)
		
		# update model
		Settings().moveDownProfile(profile)
		
		# update ui
		nextIt = store.iter_next(it)
		if (nextIt):
			store.swap(it, nextIt)
	
	def _on_new_tool_clicked(self, button):
		dialog = ConfigureToolDialog()
		
		tool = Tool("New Tool", [], "", [".tex"])
		
		if not dialog.run(tool) is None:
			self._preferences.save_or_update_tool(tool)
	
	def _on_save_snippet_clicked(self, button):
		pass
	
	def _on_new_snippet_clicked(self, button):
		self._store_snippets.append([True, "Unnamed", Template("")])
	
	
		
	
#	def _on_save_tool_clicked(self, button):
#		"""
#		Update the current profile
#		"""
#		self._profile.name = self._entryProfileName.get_text()
#		self._profile.viewCommand = self._entryViewCommand.get_text()
#		self._profile.outputFile = self._entryOutputFile.get_text()
#		
#		self._profile.jobs = []
#		for row in self._store_job:
#			self._profile.jobs.append(Job(row[0], row[1], row[2]))
#		
#		Settings().updateProfile(self._profile)
	
	def _on_apply_clicked(self, button):
		self._dialog.hide()
	
	def _on_abort_clicked(self, button):
		self._dialog.hide()
	
	def _on_snippet_changed(self, treeView):
		store, it = treeView.get_selection().get_selected()
		if not it: 
			return
		
		self._template = store.get_value(it, 2)
		
		self._entry_snippet.get_buffer().set_text(self._template.source)
		
	def _on_tool_changed(self, treeView):
		"""
		The cursor in the tools view has changed
		"""
		store, it = treeView.get_selection().get_selected()
		if not it: 
			return
		
		self._profile = store.get_value(it, 1)
		
		# load profile settings

#		self._entryProfileName.set_text(self._profile.name)
#		
#		self._store_job.clear()
#		for job in self._profile.jobs:
#			self._store_job.append([job.command, job.mustSucceed, job.postProcessor])
#			
#		self._entryViewCommand.set_text(self._profile.viewCommand)
#		self._entryOutputFile.set_text(self._profile.outputFile)
		
			
	
	
	