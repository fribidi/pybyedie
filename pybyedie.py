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

def paragraph_level (types, base):

	el = 0 # embedding_level

	# P2, P3
	if base == ON:
		for i in range (len (types)):
			if types[i] in [L, AL, R]:
				if types[i] in [AL, R]:
					el = 1
			break
	elif base == L:
		el = 0
	elif base == R:
		el = 1
	else:
		assert (False)

	return el

def explicit_embeddings (types, el):

	out = []

	# X1
	cel = el # current embedding level
	dos = ON # directional override status
	stack = []

	for t in types:
		# X2
		if t == RLE:
			nel = cel + 1 + (cel % 2)
			stack.append ((cel, dos))
			if nel <= 61:
				cel = nel
				dos = ON
			continue
		# X3
		if t == LRE:
			stack.append ((cel, dos))
			nel = cel + 1 + 1 - (cel % 2)
			if nel <= 61:
				cel = nel
				dos = ON
			continue
		# X4
		if t == RLO:
			stack.append ((cel, dos))
			nel = cel + 1 + (cel % 2)
			if nel <= 61:
				cel = nel
				dos = R
			continue
		# X5
		if t == LRO:
			stack.append ((cel, dos))
			nel = cel + 1 + 1 - (cel % 2)
			if nel <= 61:
				cel = nel
				dos = L
			continue
		if t == PDF:
			if len (stack):
				cel, dos = stack.pop ()
			continue
		if t == B:
			# TODO
			pass
		if t not in [BN, RLE, LRE, RLO, LRO, PDF]:
			cct = t # current character type
			if dos == L:
				cct = L
			if dos == R:
				cct = R
			out.append ([t, cel])
			continue

	return out



def bidi_par (types, base):

	el = paragraph_level (types, base)

	elts = explicit_embeddings (types, el)

	return [x[0] for x in elts], [x[1] for x in elts]

def bidi (types, base):
	levels = []
	order = []
	# P1
	start = 0
	for i in range (len (types)):
		if types[i] == 'B':
			types, levels = bidi_par (types[start:i+1], base)
			order.extend (types)
			levels.extend (levels)
			start = i + 1
	types, levels = bidi_par (types[start:len (types)], base)
	order.extend (types)
	levels.extend (levels)
	return levels, order


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
	for f in sys.argv[1:]:
		do_tests (f)
