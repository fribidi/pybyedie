#!/usr/bin/python

# Copyright (C) 2013  Google, Inc.
#
# PyByeDie, a reference implementation of UAX#9 Unicode Bidirectional Algorithm.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# the Unicode data files and any associated documentation (the "Data Files") or
# Unicode software and any associated documentation (the "Software") to deal in
# the Data Files or Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, and/or sell copies
# of the Data Files or Software, and to permit persons to whom the Data Files or
# Software are furnished to do so, provided that (a) the above copyright
# notice(s) and this permission notice appear with all copies of the Data Files
# or Software, (b) both the above copyright notice(s) and this permission notice
# appear in associated documentation, and (c) there is clear notice in each
# modified Data File or in the Software as well as in the documentation
# associated with the Data File(s) or Software that the data or software has been
# modified.
#
# THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF THIRD
# PARTY RIGHTS. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN
# THIS NOTICE BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL
# DAMAGES, OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING
# OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA FILES OR
# SOFTWARE.
#
# Except as contained in this notice, the name of a copyright holder shall not be
# used in advertising or otherwise to promote the sale, use or other dealings in
# these Data Files or Software without prior written authorization of the
# copyright holder.
#
# Google Author(s):
#   Behdad Esfahbod

import itertools

def split_if (items, test):
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
		del acc[0]
	return items

def process_with_accumulator (items, func, accumulate, initial=None):
	'''Calls func for each item, and an accumulated value of the previous
	   items.  The accumulated value is the result of successively calling
	   accumulate on the previous accumulated value and the current item.
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
LRI	= "LRI"
RLI	= "RLI"
FSI	= "FSI"
PDI	= "PDI"

strongs = [L, R, AL]
neutrals_and_isolates = [B, S, WS, ON, FSI, LRI, RLI, PDI]
embedding_initiators = [LRE, RLE, LRO, RLO]
isolate_initiators = [LRI, RLI, FSI]

def type_for_level (n):
	return [L, R][n % 2]

class Run:
	def __init__ (self, ranges, type, level = 0, list = []):
		self.ranges = ranges
		self.type = type
		self.level = level
		self.list = list

	def __len__ (self):
		return sum (end - start for (start, end) in self.ranges)
	def __cmp__ (self, other):
		return cmp (self.ranges, other.ranges)

	def __repr__ (self):
		return "Run(%s,%s,%s%s)" % (self.ranges, self.type, self.level, \
					    "," + repr (self.list) if self.list else "")

	class Mismatch (Exception): pass
	class TypeMismatch (Mismatch): pass
	class LevelMismatch (Mismatch): pass
	class ListMismatch (Mismatch): pass

	def append (self, other):
		if self.type  != other.type:  raise Run.TypeMismatch ()
		if self.level != other.level: raise Run.LevelMismatch ()
		if self.list  != other.list:  raise Run.ListMismatch ()
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
	def last_strong_accumulator (last_strong, run):
		'''Returns the last strong type of last_strong and current run.'''
		if run.type in strongs:
			return run.type
		return last_strong


def get_paragraph_embedding_level (runs, base):

	if base == ON:
		try:
			# P2. In each paragraph, find the first character of
			# type L, AL, or R.
			first = next (r for r in runs if r.type in strongs)
			# P3. If a character is found in P2 and it is of type
			# AL or R, then set the paragraph embedding level to
			# one; otherwise, set it to zero.
			return 1 if first.type in [AL, R] else 0
		except StopIteration:
			# P3.
			return 0
	elif base == L:
		# HL1. Override P3, and set the paragraph embedding level explicitly.
		return 0
	elif base == R:
		# HL1. Override P3, and set the paragraph embedding level explicitly.
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
	invalid_count = 0

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
		if r.type in [RLE, LRE, RLO, LRO]:
			for i in range (len (r)):
				if r.type in [RLE, RLO]:
					n = state.least_greatest_odd ()
				else:
					n = state.least_greatest_even ()
				if invalid_count == 0 and State.level_would_be_valid (n):
					stack.append (state)
					if r.type in [RLE, LRE]:
						t = ON
					else:
						t = R if r.type == RLO else L
					state = State (n, t)
				else:
					invalid_count += 1

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
		if r.type == PDF:
			for i in range (len (r)):
				if invalid_count:
					invalid_count -= 1
				elif stack:
					state = stack.pop ()

		# X9. Remove all RLE, LRE, RLO, LRO, PDF, and BN codes.
		if r.type in [RLE, LRE, RLO, LRO, PDF, BN]:
			r.level = -1 # To be removed

	return Run.compact_list (r for r in runs if r.level != -1)

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

	def _N_ (this):
		'''Note: Consolidate all neutrals. The rest of the rules
		   consider all neutrals as a single run, so make it so.'''
		if this.type in neutrals_and_isolates:
			this.type = ON
	runs = Run.compact_list (process_neighbors (runs, 1, _N_))

	def N1 (prev, this, next):
		'''A sequence of neutrals takes the direction of the
		   surrounding strong text if the text on both sides has the
		   same direction. European and Arabic numbers act as if they
		   were R in terms of their influence on neutrals.
		   Start-of-level-run (sor) and end-of-level-run (eor) are
		   used at level run boundaries.'''
		if this.type == ON:
			p = R if prev.type in [R, EN, AN] else prev.type
			n = R if next.type in [R, EN, AN] else next.type
			if p == n:
				this.type = p
	runs = Run.compact_list (process_neighbors (runs, 3, N1))

	def N2 (this):
		'''Any remaining neutrals take the embedding direction.'''
		if this.type == ON:
			this.type = type_for_level (this.level)
	runs = Run.compact_list (process_neighbors (runs, 1, N2))

	return runs

def resolve_implicit_levels (runs):

	def I1 (this):
		'''For all characters with an even (left-to-right) embedding
		   direction, those of type R go up one level and those of
		   type AN or EN go up two levels.'''
		if this.level % 2 == 0:
			if this.type == R:
				this.level += 1
			if this.type in [AN, EN]:
				this.level += 2
	runs = Run.compact_list (process_neighbors (runs, 1, I1))

	def I2 (this):
		'''For all characters with an odd (right-to-left) embedding
		   direction, those of type L, EN or AN go up one level.'''
		if this.level % 2 == 1:
			if this.type in [L, EN, AN]:
				this.level += 1
	runs = Run.compact_list (process_neighbors (runs, 1, I2))

	return runs

def resolve_level_run (runs, sor, eor):

	# Create sentinels for sor, eor
	runs = [Run ([(-1,-1)], sor, -1)] + runs + [Run ([(2147483647,2147483647)], eor, -1)]
	# The functions we call don't have to worry about sor, eor

	runs = resolve_weak_types (runs)
	runs = resolve_neutral_types (runs)
	runs = resolve_implicit_levels (runs)

	# Drop sentinels and return.
	return [r for r in runs if r.level != -1]

def resolve_per_level_run_stuff (runs, par_level):
	'''X10. The remaining rules are applied to each run of characters at
	   the same level. For each run, determine the start-of-level-run (sor)
	   and end-of-level-run (eor) type, either L or R. This depends on the
	   higher of the two levels on either side of the boundary (at the
	   start or end of the paragraph, the level of the "other" run is the
	   base embedding level). If the higher level is odd, the type is R;
	   otherwise, it is L.'''

	runs = split_if (runs, lambda a,b: a.level != b.level)
	# runs now is list of list of runs at same level

	levels = [r[0].level for r in runs]
	sors = [type_for_level (max (pair)) for pair in zip (levels, [par_level]+levels[:-1])]
	eors = [type_for_level (max (pair)) for pair in zip (levels[1:]+[par_level], levels )]
	del levels

	runs = map (resolve_level_run, runs, sors, eors)

	# Put together and return,
	return sum (runs, [])

def do_per_line_stuff (levels, par_level, orig_types):
	'''L1. On each line, reset the embedding level of the following
	   characters to the paragraph embedding level:

	       1. Segment separators,
	       2. Paragraph separators,
	       3. Any sequence of whitespace characters preceding a segment
	          separator or paragraph separator, and
	       4. Any sequence of white space characters at the end of the line.

	       * The types of characters used here are the original types, not
	         those modified by the previous phase.

	       * Because a Paragraph Separator breaks lines, there will be at
	         most one per line, at the end of that line.'''

	assert (len (levels) == len (orig_types))

	# Do it all.
	reset = True
	for i in reversed (range (len (levels))):
		if levels[i] == -1:
			continue
		if orig_types[i] in [S, B]:
			reset = True
		elif orig_types[i] not in [WS, FSI, LRI, RLI, PDI]:
			reset = False
		if reset:
			levels[i] = par_level

	return levels

def reorder_line (levels):
	'''L2. From the highest level found in the text to the lowest odd level
	   on each line, including intermediate levels not actually present in
	   the text, reverse any contiguous sequence of characters that are at
	   that level or higher.'''

	reorder = [r for r in enumerate (levels) if r[1] != -1]
	# reorder now is tuples of (index,level).

	if not reorder:
		return reorder

	highest_level = max (r[1] for r in reorder)
	lowest_level = min (r[1] for r in reorder)
	if lowest_level % 2 == 0:
		lowest_level += 1

	for level in range (highest_level, lowest_level - 1, -1):
		# Break into contiguous sequences.
		seqs = split_if (reorder, lambda a,b: (a[1] >= level) != (b[1] >= level))
		# Reverse high-enough sequences.
		seqs = [list (reversed (s)) if s[0][1] >= level else s for s in seqs]
		# Put it back together.
		reorder = sum (seqs, [])

	# Remove levels and return.
	return [r[0] for r in reorder]

def create_isolated_run_lists (types):

	base_runs = runs = []
	stack = []

	for i, t in enumerate (types):

		run = Run ([(i, i+1)], t, 0)

		if t in isolate_initiators:
			runs.append (run)
			stack.append (runs)
			runs = run.list = []
			run.orig_type = run.type
			continue

		if t == PDI and stack:
			runs = stack.pop ()

		try:
			runs[-1].append (run)
		except Run.Mismatch:
			runs.append (run)
		except IndexError:
			runs.append (run)

	return base_runs

def bidi_par_no_isolates (runs, base, min_level):

	run_lists = []

	par_level = get_paragraph_embedding_level (runs, base)

	# Adjust par_level to be at least min_level
	par_level = min_level + (1 if par_level % 2 != min_level % 2 else 0)

	runs = do_explicit_levels_and_directions (runs, par_level)

	# Recurse on sub-isolates
	for r in runs:
		if not r.list:
			continue
		s_runs = r.list
		s_base = {FSI:ON,LRI:L,RLI:R}[r.orig_type]
		s_min_level = r.level + 1
		(s_runs, s_par_level) = bidi_par_no_isolates (s_runs, s_base, s_min_level)
		r.list = []
		run_lists.append (s_runs)
	runs = Run.compact_list (runs)

	runs = resolve_per_level_run_stuff (runs, par_level)
	run_lists.append (runs)

	return (sum (run_lists, []), par_level)

def bidi_par (types, base):

	# Create runs.
	runs = create_isolated_run_lists (types)

	runs, par_level = bidi_par_no_isolates (runs, base, 0)

	# Populate levels
	levels = [-1] * len (types)
	for run in runs:
		for r in run.ranges:
			for i in range (*r):
				levels[i] = run.level

	# Break lines here.  For each line do:

	levels = do_per_line_stuff (levels, par_level, types)

	reorder = reorder_line (levels)

	return (levels, reorder)

def bidi (types, base):

	# P1. Split the text into separate paragraphs. A paragraph separator
	# is kept with the previous paragraph. Within each paragraph, apply
	# all the other rules of this algorithm.
	pars = split_if (types, lambda t,_: t == B)
	pars = [bidi_par (par, base) for par in pars]
	# pars now has (levels,reorder) per paragraph.

	# Merge them and return.
	return (sum ((p[0] for p in pars), []), sum ((p[1] for p in pars), []))


def test_case (lineno, types, base, expected_levels, expected_order):

	(levels, order) = bidi (types, base)
	if levels == expected_levels and order == expected_order:
		return True

	print "failure on line", lineno
	print "input is:", ' '.join (types)
	print "base dir:", base
	print "expected levels:", ' '.join (str (x) if x != -1 else 'x' for x in expected_levels)
	print "returned levels:", ' '.join (str (x) if x != -1 else 'x'  for x in levels)
	print "expected order:", ' '.join (str (x) for x in expected_order)
	print "returned order:", ' '.join (str (x) for x in order)
	print
	return False

def test_file (f):

	num_fails = 0
	lineno = 0
	for l in file (f):
		lineno += 1

		if not len (l) or l[0] == '\n' or l[0] == '#':
			continue

		if l[0] == '@':

			if l.startswith ('@Levels:'):
				expected_levels = [int (i) if i != 'x' else -1 for i in l[8:].split ()]
				continue
			if l.startswith ('@Reorder:'):
				expected_order = [int (i) for i in l[9:].split ()]
				continue
			continue

		types, flags = l.split (';')
		types = types.split ()
		flags = int (flags)

		for f in range (0, 3):
			if not ((1<<f) & flags):
				continue
			base = ['ON', 'L', 'R'][f]
			if not test_case (lineno, types, base, \
					  expected_levels, expected_order):
				num_fails += 1

	if num_fails:
		print "%d error" % num_fails

	return num_fails == 0


if __name__ == '__main__':

	import sys

	args = sys.argv[1:]

	if not sys.argv[1:]:
		print >>sys.stderr, "Usage:\n  pybyedie [--rtl/--ltr/--auto] [TYPE]...\nor\n  pybyedie --test [FILE]..."
		sys.exit (1)

	if args[0] == "--test":
		del args[0]
		success = True
		for f in args:
			success = test_file (f) and success
		sys.exit (0 if success else 1)

	base = ON
	if args[0] == "--rtl":
		base = R
		del args[0]
	if args[0] == "--ltr":
		base = L
		del args[0]
	if args[0] == "--auto":
		base = ON
		del args[0]

	(levels, reorder) = bidi (args, base)
	print "Levels:  %s" % ' '.join (str (l) if l != -1 else 'x' for l in levels)
	print "Reorder: %s" % ' '.join (str (l) for l in reorder)
