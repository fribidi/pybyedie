#!/usr/bin/python

L	= "L"
R	= "R"
AL	= "AL"
EN	= "EN"
ES	= "ES"
ET	= "ET"
AN	= "AN"
CS	= "CS"
NSM	= "NSM"
BN	= "BN"
B	= "B"
S	= "S"
WS	= "WS"
ON	= "ON"
LRE	= "LRE"
LRO	= "LRO"
RLE	= "RLE"
RLO	= "RLO"
PDF	= "PDF"

class Run:
	def __init__ (self, ranges, type, level):
		self.ranges = ranges
		self.type = type
		self.level = level

	def __repr__ (self):
		return "Run(%s,%s,%s)" % (self.ranges, self.type, self.level)

	def __cmp__ (self, other):
		return cmp (self.ranges, other.ranges)

	@staticmethod
	def sentinel ():
		return Run ([(-1, 0)], None, -1)

	class Mismatch (Exception): pass
	class TypeMismatch (Mismatch): pass
	class LevelMismatch (Mismatch): pass

	def append (self, other):
		if self.type  != other.type:  raise Run.TypeMismatch ()
		if self.level != other.level: raise Run.LevelMismatch ()
		assert self.ranges[-1][1] <= other.ranges[0][0]
		if self.ranges[-1][1] == other.ranges[0][0]:
			self.ranges[-1] = (self.ranges[-1][0], other.ranges[0][1])
			self.ranges.extend (other.ranges[1:])
		else:
			self.ranges.extend (other.ranges)

	@staticmethod
	def compact_list (runs):

		def append_run (runs, run):
			try:
				runs[-1].append (run)
				return runs
			except Run.Mismatch: pass
			except IndexError: pass
			runs.append (run)
			return runs
		return reduce (append_run, runs, [])

	@staticmethod
	def uncompact_list (runs):

		return [Run (range, run.type, run.level) \
			for run in runs \
			for range in run.ranges]

	@staticmethod
	def merge_lists (run_lists):
		return Run.compact_list (sorted (sum ((Run.uncompact_list (r) \
						       for r in run_lists), \
						      [])))


def get_paragraph_embedding_level (runs, base):

	if base == ON:
		try:
			# P2
			first = (r for r in runs if r.type in [L, AL, R]).next ()
			# P3
			return 1 if first.type in [AL, R] else 0
		except StopIteration:
			# P3
			return 0
	elif base == L:
		# HL1
		return 0
	elif base == R:
		# HL1
		return 1
	else:
		assert (False)

def get_explicit_levels_and_directions (runs, par_level):

	class State:
		def __init__ (self, level, dir):
			self.level = level
			self.dir = dir

		def least_greatest_odd (self):
			return self.level + 1 + (self.level % 2)
		def least_greatest_even (self):
			return self.level + 1 + 1-(self.level % 2)

		@staticmethod
		def level_would_be_valid (n):
			return 0 <= n <= 61

	stack = []

	# X1
	state = State (par_level, ON)
	for r in runs:
		# X2
		if r.type == RLE:
			stack.append (state)
			n = state.least_greatest_odd ()
			if State.level_would_be_valid (n):
				state = State (n, ON)
		# X3
		if r.type == LRE:
			stack.append (state)
			n = state.least_greatest_even ()
			if State.level_would_be_valid (n):
				state = State (n, ON)
		# X4
		if r.type == RLO:
			stack.append (state)
			n = state.least_greatest_odd ()
			if State.level_would_be_valid (n):
				state = State (n, R)
		# X5
		if r.type == LRO:
			stack.append (state)
			n = state.least_greatest_even ()
			if State.level_would_be_valid (n):
				state = State (n, L)
		# X8
		# Note: X8 needs to be done before X6.  Spec bug.
		if r.type == B:
			if len (stack):
				state = stack[0]
				stack = []
		# X6
		if r.type not in [BN, RLE, LRE, RLO, LRO, PDF]:
			r.level = state.level
			if state.dir != ON:
				r.type = state.dir
		# X7
		if r.type == PDF:
			state = stack.pop ()
			continue
		# X9
		if r.type in [RLE, LRE, RLO, LRO, PDF, BN]:
			r.level = -1 # To be removed
	return runs


def bidi_par (runs, base):

	par_level = get_paragraph_embedding_level (runs, base)

	runs = get_explicit_levels_and_directions (runs, par_level)

	# Separate removed characters, to add back after we're done.
	removed = Run.compact_list (r for r in runs if r.level == -1)
	runs = Run.compact_list (r for r in runs if r.level != -1)

	# Do more bidi

	return Run.merge_lists ([runs, removed])

def bidi (types, base):

	runs = Run.compact_list (Run ([(i, i+1)], t, 0) for i, t in enumerate (types))

	# P1
	def split_at_B (run_lists, run):
		run_lists[-1].append (run)
		if run.type == B:
			run_lists.append ([])
		return run_lists
	pars = reduce (split_at_B, runs, [[]])
	runs = sum ((bidi_par (par, base) for par in pars), [])
	return runs

import sys
types = sys.argv[1:]
print bidi (types, ON)

def do_tests (f):

	lineno = 0
	for l in file (f):
		lineno += 1

		if not len (l) or l[0] == '\n' or l[0] == '#':
			continue

		if l[0] == '@':

			if l.startswith ('@Levels:'):
				expected_levels = l[8:].split ()
				continue
			if l.startswith ('@Reorder:'):
				expected_order = l[9:].split ()
				continue
			continue

		types, flags = l.split (';')
		types = types.split ()
		flags = int (flags)

		for f in range (0, 3):
			if not ((1<<f) & flags):
				continue
			base = ['ON', 'L', 'R'][f]
			(levels, order) = bidi (types, base)
			if not (levels == expected_levels and order == expected_order):
				print "failure on line", lineno
				print "int is:", ' '.join (types)
				print "base dir:", base
				print "expected levels:", ' '.join (expected_levels)
				print "returned levels:", ' '.join (str(x) for x in levels)
				print "expected order:", ' '.join (expected_order)
				print "returned order:", ' '.join (str(x) for x in order)
				print


if __name__ == '__main__':

	import sys
	#for f in sys.argv[1:]:
	#	do_tests (f)
