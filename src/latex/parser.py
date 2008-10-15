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
latex.parser

LaTeX parser and object model
"""

from logging import getLogger
from os.path import exists
from os import popen, system
from re import compile

from ..util import caught, escape
from ..issues import Issue


class Node(list):
	"""
	This is the base class of the LaTeX object model
	"""
	
	DOCUMENT, COMMAND, MANDATORY_ARGUMENT, OPTIONAL_ARGUMENT, TEXT, EMBRACED = range(6)
	
	def __init__(self, type, value=None):
		self.type = type
		self.value = value
		self.parent = None
		
		# this indicates if an argument is closed or not
		# (only used by the PrefixParser)
		self.closed = False
	
	def firstOfType(self, type):
		"""
		Return the first child node of a given type
		"""
		for node in self:
			if node.type == type:
				return node
		raise IndexError
	
	def filter(self, type):
		"""
		Return all child nodes of this node having a certain type
		"""
		return [node for node in self if node.type == type]
	
	@property
	def xml(self):
		"""
		Return an XML representation of this node (for debugging)
		"""
		if self.type == self.COMMAND:
			content = "".join([node.xml for node in self])
			if len(content):
				return "<command name=\"%s\">%s</command>" % (escape(self.value), content)
			else:
				return "<command name=\"%s\" />" % escape(self.value)
		elif self.type == self.MANDATORY_ARGUMENT:
			return "<mandatory>%s</mandatory>" % "".join([node.xml for node in self])
		elif self.type == self.OPTIONAL_ARGUMENT:
			return "<optional>%s</optional>" % "".join([node.xml for node in self])
		elif self.type == self.TEXT:
			return escape(self.value)
		elif self.type == self.DOCUMENT:
			return "<document>%s</document>" % "".join([node.xml for node in self])
		elif self.type == self.EMBRACED:
			return "<embraced>%s</embraced>" % "".join([node.xml for node in self])
	
	@property
	def xmlPrefix(self):
		"""
		Return an XML representation of this node (for debugging)
		
		This is for the prefix mode, so we print if the arguments are closed or not
		"""
		if self.type == self.COMMAND:
			content = "".join([node.xmlPrefix for node in self])
			if len(content):
				return "<command name=\"%s\">%s</command>" % (self.value, content)
			else:
				return "<command name=\"%s\" />" % self.value
		elif self.type == self.MANDATORY_ARGUMENT:
			return "<mandatory closed=%s>%s</mandatory>" % (self.closed, "".join([node.xmlPrefix for node in self]))
		elif self.type == self.OPTIONAL_ARGUMENT:
			return "<optional closed=%s>%s</optional>" % (self.closed, "".join([node.xmlPrefix for node in self]))
		elif self.type == self.TEXT:
			return escape(self.value)
		elif self.type == self.DOCUMENT:
			return "<document>%s</document>" % "".join([node.xmlPrefix for node in self])
		elif self.type == self.EMBRACED:
			return "<embraced>%s</embraced>" % "".join([node.xmlPrefix for node in self])
	
	def __str__(self):
		"""
		Return the original LaTeX representation of this node
		"""
		if self.type == self.COMMAND:
			return "\\%s%s" % (self.value, "".join([str(node) for node in self]))
		elif self.type == self.MANDATORY_ARGUMENT or self.type == self.EMBRACED:
			return "{%s}" % "".join([str(node) for node in self])
		elif self.type == self.OPTIONAL_ARGUMENT:
			return "[%s]" % "".join([str(node) for node in self])
		elif self.type == self.TEXT:
			return self.value
		elif self.type == self.DOCUMENT:
			return "".join([str(node) for node in self])
	
	@property
	def innerText(self):
		"""
		Return the concatenated values of all TEXT child nodes
		"""
		return "".join([child.value for child in self if child.type == Node.TEXT])
	
	@property
	def markup(self):
		"""
		Return the concatenated markup values of this node and all child nodes
		"""
		if self.type == self.COMMAND:
			return "<span color=\"grey\">\\%s</span>%s" % (self.value, "".join([node.markup for node in self]))
		elif self.type == self.MANDATORY_ARGUMENT or self.type == self.EMBRACED:
			return "<span color=\"grey\">{</span>%s<span color=\"grey\">}</span>" % "".join([node.markup for node in self])
		elif self.type == self.OPTIONAL_ARGUMENT:
			return "<span color=\"grey\">[</span>%s<span color=\"grey\">]</span>" % "".join([node.markup for node in self])
		elif self.type == self.TEXT:
			return escape(self.value)
		elif self.type == self.DOCUMENT:
			return "".join([node.markup for node in self])
	
	@property
	def innerMarkup(self):
		"""
		Return the concatenated markup values of only the child nodes
		"""
		return "".join([node.markup for node in self])
	
	def append(self, node):
		"""
		Append a child node and store a back-reference
		"""
		node.parent = self
		list.append(self, node)
	
	def find(self, value):
		"""
		Find child node with given value (recursive, so grand-children are found, too)
		"""
		# TODO
		

class Document(Node):
	"""
	An extended Node with special methods for a LaTeX document
	"""
	
	def __init__(self, file):
		Node.__init__(self, Node.DOCUMENT, file)
		
		self._is_master_called = False
		self._is_master = False
	
	def _do_is_master(self):
		# TODO: this should be recursive
		
		for node in self:
			if node.type == Node.COMMAND and node.value == "begin":
				if node.firstOfType(Node.MANDATORY_ARGUMENT).innerText == "document":
					return True
		return False
	
	@property
	def is_master(self):
		"""
		@return: True if this document is a master document
		"""
		
		# TODO: determine this while parsing
		
		if not self._is_master_called:
			self._is_master = self._do_is_master()
			self._is_master_called = True
		return self._is_master


class LocalizedNode(Node):
	"""
	This Node type holds the start and end offsets of the substring it belongs to
	in the source
	"""
	def __init__(self, type, start, end, value=None, file=None):
		Node.__init__(self, type, value)
		self.start = start
		self.end = end
		self.file = file
	
	@property
	def lastEnd(self):
		"""
		Return the end of the last child node or of this node if
		it doesn't have children.
		"""
		try:
			return self[-1].end
		except IndexError:
			return self.end
				

class FatalParseException(Exception):
	"""
	This raised of the Parser faces a fatal error and cannot continue
	"""


from lexer import Lexer, Token


class LaTeXParser(object):
	"""
	A tree parser building an object model of nodes
	"""
	
	# TODO: remove second parse method
	
	@caught
	def _parse(self, string, documentNode, file, issue_handler):
		"""
		@deprecated: use parse_string() and issues() instead
		"""
		self._file = file
		self._issue_handler = issue_handler
		
		# TODO: include comments into the model
		self.comments = []
		
		self._stack = [documentNode]
		
		callables = {
				Token.COMMAND : self.command, 
				Token.TEXT : self.text, 
				Token.BEGIN_CURLY : self.beginCurly,
				Token.END_CURLY : self.endCurly, 
				Token.BEGIN_SQUARE : self.beginSquare, 
				Token.END_SQUARE : self.endSquare,
				Token.COMMENT : self.comment, 
				Token.VERBATIM : self.verbatim }
		
		try:
			for token in Lexer(string):
				callables[token.type].__call__(token.value, token.offset)
		except FatalParseException:
			return
		
		# check stack remainder
		for node in self._stack:
			if node.type == Node.MANDATORY_ARGUMENT or node.type == Node.EMBRACED:
				self._issue_handler.issue(Issue("Unclosed {", node.start, node.start + 1, self._file, Issue.SEVERITY_ERROR))
			elif node.type == Node.OPTIONAL_ARGUMENT:
				self._issue_handler.issue(Issue("Unclosed [", node.start, node.start + 1, self._file, Issue.SEVERITY_ERROR))
	
	def parse(self, string, file, issue_handler):
		"""
		@param string: LaTeX source
		@param from_filename: filename from where the source is read (this is used to tag
				parts of the model)
				
		@rtype: Document
		"""
		document_node = Document(file)
		self._parse(string, document_node, file, issue_handler)
		
		return document_node
	
	# TODO: rename methods from "command()" to "_on_command()"
	
	def command(self, value, offset):
		top = self._stack[-1]
		
		if top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = LocalizedNode(Node.COMMAND, offset, offset + len(value) + 1, value, self._file)
			top.append(node)
			self._stack.append(node)
			
		elif top.type == Node.COMMAND \
				or top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.command(value, offset)
			except IndexError:
				self._issue_handler.issue(Issue("Undefined Parse Error", offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
	
	def text(self, value, offset):
		top = self._stack[-1]

		if top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = LocalizedNode(Node.TEXT, offset, offset + len(value), value, self._file)
			top.append(node)
			self._stack.append(node)
			
		elif top.type == Node.COMMAND:
			self._stack.pop()
			self.text(value, offset)
			
		elif top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.text(value, offset)
			except IndexError:
				self._issue_handler.issue(Issue("Undefined Parse Error", offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
		else:
			# TODO: possible?
			self._issue_handler.issue(Issue("Unexpected TEXT token with %s on stack" % top.type, offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
	
	def beginCurly(self, value, offset):
		top = self._stack[-1]
		
		if top.type == Node.COMMAND:
			node = LocalizedNode(Node.MANDATORY_ARGUMENT, offset, offset + 1, file=self._file)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = LocalizedNode(Node.EMBRACED, offset, offset + 1, file=self._file)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.beginCurly(value, offset)
			except IndexError:
				self._issue_handler.issue(Issue("Undefined Parse Error", offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
		else:
			# TODO: possible?
			self._issue_handler.issue(Issue("Unexpected BEGIN_CURLY token with %s on stack" % top.type, offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
	
	def endCurly(self, value, offset):
		try:
			# pop from stack until MANDATORY_ARGUMENT or EMBRACED
			while True:
				top = self._stack[-1]
				if top.type == Node.MANDATORY_ARGUMENT or top.type == Node.EMBRACED:
					node = self._stack.pop()
					break
				self._stack.pop()
				
			# set end offset of MANDATORY_ARGUMENT or EMBRACED
			node.end = offset + 1
		except IndexError:
			self._issue_handler.issue(Issue("Encountered <b>}</b> without <b>{</b>", offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
			# we cannot continue after that
			raise FatalParseException
	
	def beginSquare(self, value, offset):
		top = self._stack[-1]
		if top.type == Node.COMMAND:
			node = LocalizedNode(Node.OPTIONAL_ARGUMENT, offset, offset + 1, file=self._file)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.TEXT:
			top.value += "["
		
		elif top.type == Node.MANDATORY_ARGUMENT:
			node = LocalizedNode(Node.TEXT, offset, offset + 1, "[", self._file)
			top.append(node)
			self._stack.append(node)
		
		else:
			self._issue_handler.issue(Issue("Unexpected BEGIN_SQUARE token with %s on stack" % top.type, offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
	
	def endSquare(self, value, offset):
		try:
			node = [node for node in self._stack if node.type == Node.OPTIONAL_ARGUMENT][-1]
			
			# open optional argument found 
			# this square closes it, so pop stack until there
			
			while self._stack[-1].type != Node.OPTIONAL_ARGUMENT:
				self._stack.pop()
			node = self._stack.pop()
			node.end = offset + 1
			
		except IndexError:
			# no open optional argument, so this "]" is TEXT
			
			top = self._stack[-1]
			if top.type == Node.TEXT:
				top.value += "]"
				
			elif top.type == Node.COMMAND:
				try:
					self._stack.pop()
					self.endSquare(value, offset)
				except IndexError:
					self._issue_handler.issue(Issue("Undefined Parse Error", offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
			
			elif top.type == Node.MANDATORY_ARGUMENT or top.type == Node.DOCUMENT or top.type == Node.OPTIONAL_ARGUMENT:
				node = LocalizedNode(Node.TEXT, offset, offset + 1, "]", self._file)
				top.append(node)
				self._stack.append(node)
			
			else:
				self._issue_handler.issue(Issue("Unexpected END_SQUARE token with %s on stack and no optional argument" % top.type, offset, offset + 1, self._file, Issue.SEVERITY_ERROR))
	
	def comment(self, value, offset):
		# TODO: this should go to the model
		
		self.comments.append([value, offset])
		
	def verbatim(self, value, offset):
		pass


class PrefixParser(object):
	"""
	A light-weight LaTeX parser used for parsing just a prefix in
	the code completion.
	
	The differences between the full parser and this one include:
	 * we don't collect issues (we just raise an exception)
	 * we don't store node offsets
	 * we indicate whether the last argument is closed or not
	"""
	
	# TODO: use another Lexer here that doesn't count offsets (faster)
	
	def parse(self, string, documentNode):
		
		# TODO: change semantic 
		
		self._stack = [documentNode]
		
		callables = {Token.COMMAND : self.command, 
					 Token.TEXT : self.text, 
					 Token.BEGIN_CURLY : self.beginCurly,
					 Token.END_CURLY : self.endCurly, 
					 Token.BEGIN_SQUARE : self.beginSquare, 
					 Token.END_SQUARE : self.endSquare,
					 Token.COMMENT : self.comment, 
					 Token.VERBATIM : self.verbatim}
		
		try:
			for token in Lexer(string, skipWs=False, skipComment=False):
				callables[token.type].__call__(token.value)
		except FatalParseException:
			return
		
	def command(self, value):
		top = self._stack[-1]
		
		if top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = Node(Node.COMMAND, value)
			top.append(node)
			self._stack.append(node)
			
		elif top.type == Node.COMMAND \
				or top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.command(value)
			except IndexError:
				raise FatalParseException
	
	def text(self, value):
		top = self._stack[-1]

		if top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = Node(Node.TEXT, value)
			top.append(node)
			self._stack.append(node)
			
		elif top.type == Node.COMMAND:
			self._stack.pop()
			self.text(value)
			
		elif top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.text(value)
			except IndexError:
				raise FatalParseException
		else:
			# TODO: possible?
			raise FatalParseException
	
	def beginCurly(self, value):
		top = self._stack[-1]
		
		if top.type == Node.COMMAND:
			node = Node(Node.MANDATORY_ARGUMENT)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.DOCUMENT \
				or top.type == Node.MANDATORY_ARGUMENT \
				or top.type == Node.OPTIONAL_ARGUMENT \
				or top.type == Node.EMBRACED:
			node = Node(Node.EMBRACED)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.TEXT:
			try:
				self._stack.pop()
				self.beginCurly(value)
			except IndexError:
				raise FatalParseException
		else:
			# TODO: possible?
			raise FatalParseException
	
	def endCurly(self, value):
		try:
			# pop from stack until MANDATORY_ARGUMENT or EMBRACED
			while True:
				top = self._stack[-1]
				if top.type == Node.MANDATORY_ARGUMENT or top.type == Node.EMBRACED:
					node = self._stack.pop()
					break
				self._stack.pop()
				
			node.closed = True
		except IndexError:
			raise FatalParseException
	
	def beginSquare(self, value):
		top = self._stack[-1]
		if top.type == Node.COMMAND:
			node = Node(Node.OPTIONAL_ARGUMENT)
			top.append(node)
			self._stack.append(node)
		
		elif top.type == Node.TEXT:
			top.value += "["
		
		elif top.type == Node.MANDATORY_ARGUMENT:
			node = Node(Node.TEXT, "[")
			top.append(node)
			self._stack.append(node)
		
		else:
			raise FatalParseException
	
	def endSquare(self, value):
		try:
			# check whether an optional argument is open at all
			#
			# for this we address the top OPTIONAL_ARGUMENT node on the stack, if it doesn't
			# exist an IndexError is thrown
			node = [node for node in self._stack if node.type == Node.OPTIONAL_ARGUMENT][-1]
			
			# open optional argument found 
			# this square closes it, so pop stack until there
			
			while self._stack[-1].type != Node.OPTIONAL_ARGUMENT:
				self._stack.pop()
			node = self._stack.pop()
			node.closed = True
			
		except IndexError:
			# no open optional argument, so this "]" is TEXT
			
			top = self._stack[-1]
			if top.type == Node.TEXT:
				top.value += "]"
				
			elif top.type == Node.COMMAND:
				try:
					self._stack.pop()
					self.endSquare(value)
				except IndexError:
					raise FatalParseException
			
			elif top.type == Node.MANDATORY_ARGUMENT or top.type == Node.DOCUMENT or top.type == Node.OPTIONAL_ARGUMENT:
				node = Node(Node.TEXT, "]")
				top.append(node)
				self._stack.append(node)
			
			else:
				raise FatalParseException
	
	def comment(self, value):
		pass
		
	def verbatim(self, value):
		pass


# TODO: we should extract tasks when calling comment() and add them as an Issue


class TaskExtractor(object):
	"""
	This extracts TODO and FIXME comments and creates Issue objects of
	type TASK
	"""
	
	# TODO: this should walk through a document model
	
	_PATTERN = compile("(TODO|FIXME)\w?\:?(?P<text>.*)")
	
	def extract(self, comments):
		issues = []
		
		for value, offset in comments:
			match = self._PATTERN.search(value)
			if match:
				text = match.group("text").strip()
				
				# TODO: +1 ?
				issues.append(Issue("<i>%s</i>" % text, Issue.TASK, offset + match.start(), offset + match.end() + 1))
		
		return issues


		