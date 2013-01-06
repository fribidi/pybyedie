#!/usr/bin/python


def split (items, test):
	'''Calls test with each two successive members of items,
	   and if test returns True, cuts the list at that location.
	   Returns list of non-empty lists.'''
	if not items:
		return []
	last = items[0]
	out = [[last]]
	for item in items[1:]:
		if test  (last, item):
			out.append ([])
		out[-1].append (item)
		last = item
	return out

def process_neighbors (items, n, func):
	'''Calls func with n parameters, for every successive n members of items.
	   Returns items when done.'''
	if len (items) < n:
		return items
	acc = items[:n - 1]
	for item in items[n - 1:]:
		acc.append (item)
		func (*acc)
		acc[:1] = []
	return items

def process_with_accumulator (items, func, accumulate, initial=None):
	'''Calls func for each item, and an accumulated value of the previous
	   items.  The accumulated value is the result of successively calling
	   accumulate on the previous accmulated value and the current item.
	   Accumulated value is initialized to initial.  Returns items when done.'''
	acc = initial
	for item in items:
		func (item, acc)
		acc = accumulate (acc, item)
	return items


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

strongs = [L, R, AL]
neutrals =  [B, S, WS, ON]

def type_for_level (n):
	return [L, R][n % 2]

class Run:
	def __init__ (self, ranges, type, level):
		self.ranges = ranges
		self.type = type
		self.level = level

	def __len__ (self):
		return sum (end - start for (start, end) in self.ranges)
	def __cmp__ (self, other):
		return cmp (self.ranges, other.ranges)

	def __repr__ (self):
		return "Run(%s,%s,%s)" % (self.ranges, self.type, self.level)

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

	@staticmethod
	def last_strong_accumulator (last, run):
		'''Remembers the last strong type seen.'''
		if run.type in strongs:
			return run.type
		return last


def get_paragraph_embedding_level (runs, base):

	if base == ON:
		try:
			# P2
			first = (r for r in runs if r.type in strongs).next ()
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

def do_explicit_levels_and_directions (runs, par_level):

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

	# X1. Begin by setting the current embedding level to the paragraph
	# embedding level. Set the directional override status to neutral.
	# Process each character iteratively, applying rules X2 through X9.
	# Only embedding levels from 0 to 61 are valid in this phase.
	state = State (par_level, ON)
	for r in runs:

		# X2, X3, X4, X5. With each RLE/LRE/RLO/LRO, compute the
		# next embeddeing level.  For RLE/RLO that would be the
		# least greater odd value, for LRE/LRO the least greater
		# even value.
		#
		#     a. If this new level would be valid, then this embedding
		#        code is valid. Remember (push) the current embedding
		#        level and override status. Reset the current level to
		#        this new level, and reset the override status to
		#        neutral for RLE/LRE, or to R/L for RLO/LRO respectively.
		#
		#     b. If the new level would not be valid, then this code is
		#        invalid. Do not change the current level or override
		#        status.
		#
		# Note: We always push onto the stack even for invalid levels.
		# This makes finding the "matching" state for PDFs trivial.
		if r.type in [RLE, LRE, RLO, LRO]:
			stack.append (state)
			if r.type in [RLE, RLO]:
				n = state.least_greatest_odd ()
			else:
				n = state.least_greatest_even ()
			if State.level_would_be_valid (n):
				if r.type in [RLE, LRE]:
					t = ON
				else:
					t = R if r.type == RLO else L
				state = State (n, t)

		# X8. All explicit directional embeddings and overrides
		# are completely terminated at the end of each paragraph.
		# Paragraph separators are not included in the embedding.
		#
		# Note: X8 needs to be done before X6.  Spec bug.
		if r.type == B:
			if len (stack):
				state = stack[0]
				stack = []

		# X6. For all types besides BN, RLE, LRE, RLO, LRO, and PDF:
		#
		#     a. Set the level of the current character to the current
		#        embedding level.
		#
		#     b. Whenever the directional override status is not
		#        neutral, reset the current character type according to
		#        the directional override status.
		if r.type not in [BN, RLE, LRE, RLO, LRO, PDF]:
			r.level = state.level
			if state.dir != ON:
				r.type = state.dir

		# X7. With each PDF, determine the matching embedding or
		# override code. If there was a valid matching code, restore
		# (pop) the last remembered (pushed) embedding level and
		# directional override.
		#
		# Note: We don't care about validity, since we pushed an
		# state even for invalid marks.
		if r.type == PDF:
			state = stack.pop ()
			continue

		# X9. Remove all RLE, LRE, RLO, LRO, PDF, and BN codes.
		if r.type in [RLE, LRE, RLO, LRO, PDF, BN]:
			r.level = -1 # To be removed

	return runs

def resolve_weak_types (runs):

	def W1 (prev, this):
		'''Examine each nonspacing mark (NSM) in the level run, and
		   change the type of the NSM to the type of the previous
		   character. If the NSM is at the start of the level run,
		   it will get the type of sor.'''
		if this.type == NSM:
			this.type = prev.type
	runs = Run.compact_list (process_neighbors (runs, 2, W1))

	def W2 (this, last_strong):
		'''Search backward from each instance of a European number
		   until the first strong type (R, L, AL, or sor) is found.
		   If an AL is found, change the type of the European number
		   to Arabic number.'''
		if this.type == EN and last_strong == AL:
			this.type = AN
	runs = Run.compact_list (process_with_accumulator (runs, W2, \
							   Run.last_strong_accumulator, ON))

	def W3 (this):
		'''Change all ALs to R.'''
		if this.type == AL:
			this.type = R
	runs = Run.compact_list (process_neighbors (runs, 1, W3))

	def W4 (prev, this, next):
		'''A single European separator between two European numbers
		   changes to a European number. A single common separator
		   between two numbers of the same type changes to that type.'''
		if len (this) == 1:
			if this.type == ES and prev.type == next.type == EN:
				this.type = EN
			if this.type == CS and prev.type == next.type and \
			   prev.type in [EN, AN]:
				this.type = prev.type
	runs = Run.compact_list (process_neighbors (runs, 3, W4))

	def W5 (prev, this, next):
		'''A sequence of European terminators adjacent to European
		   numbers changes to all European numbers.'''
		if this.type == ET and EN in [prev.type, next.type]:
			this.type = EN
	runs = Run.compact_list (process_neighbors (runs, 3, W5))

	def W6 (this):
		'''Otherwise, separators and terminators change to Other Neutral.'''
		if this.type in [ET, ES, CS]:
			this.type = ON
	runs = Run.compact_list (process_neighbors (runs, 1, W6))

	def W7 (this, last_strong):
		'''Search backward from each instance of a European number
		   until the first strong type (R, L, or sor) is found. If
		   an L is found, then change the type of the European number
		   to L.'''
		if this.type == EN and last_strong == L:
			this.type = L
	runs = Run.compact_list (process_with_accumulator (runs, W7, \
							   Run.last_strong_accumulator, ON))

	return runs

def resolve_neutral_types (runs):

	def N1 (prev, this, next):
		'''A sequence of neutrals takes the direction of the
		   surrounding strong text if the text on both sides has the
		   same direction. European and Arabic numbers act as if they
		   were R in terms of their influence on neutrals.
		   Start-of-level-run (sor) and end-of-level-run (eor) are
		   used at level run boundaries.'''
		if this.type in neutrals:
			p = R if prev.type in [R, EN, AN] else L
			n = R if next.type in [R, EN, AN] else L
			if p == n:
				this.type = p
	runs = Run.compact_list (process_neighbors (runs, 3, N1))

	def N2 (this):
		'''Any remaining neutrals take the embedding direction.'''
		if this.type in neutrals:
			this.type = type_for_level (this.level)
	runs = Run.compact_list (process_neighbors (runs, 1, N2))

	return runs

def resolve_implicit_levels (runs):

	return runs

def resolve_level_run (runs, sor, eor):

	# Create sentinels for sor, eor
	runs = [Run ((-1,0), sor, -1)] + runs + [Run ((-1,0), eor, -1)]
	# The functions we call don't have to worry about sor, eor

	runs = resolve_weak_types (runs)
	runs = resolve_neutral_types (runs)
	runs = resolve_implicit_levels (runs)

	return [r for r in runs if r.level != -1]

def resolve_per_level_run_stuff (runs, par_level):
	'''X10. The remaining rules are applied to each run of characters at
	   the same level. For each run, determine the start-of-level-run (sor)
	   and end-of-level-run (eor) type, either L or R. This depends on the
	   higher of the two levels on either side of the boundary (at the
	   start or end of the paragraph, the level of the "other" run is the
	   base embedding level). If the higher level is odd, the type is R;
	   otherwise, it is L.'''

	runs = split (runs, lambda a,b: a.level != b.level)
	# runs now is list of list of runs at same level

	levels = [r[0].level for r in runs]
	sors = [type_for_level (max (pair)) for pair in zip (levels, [par_level]+levels[:-1])]
	eors = [type_for_level (max (pair)) for pair in zip (levels[1:]+[par_level], levels )]
	del levels

	runs = map (resolve_level_run, runs, sors, eors)

	return sum (runs, [])

def bidi_par (runs, base):

	par_level = get_paragraph_embedding_level (runs, base)

	runs = do_explicit_levels_and_directions (runs, par_level)

	# Separate removed characters, to add back after we're done.
	removed = Run.compact_list (r for r in runs if r.level == -1)
	runs = Run.compact_list (r for r in runs if r.level != -1)

	runs = resolve_per_level_run_stuff (runs, par_level)

	return Run.merge_lists ([runs, removed])

def bidi (types, base):

	runs = Run.compact_list (Run ([(i, i+1)], t, 0) for i, t in enumerate (types))

	# P1
	pars = split (runs, lambda r,_: r.type == B)

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
