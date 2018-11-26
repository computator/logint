#!/usr/bin/env python3

import re
import os.path
import sys
import dateutil.parser
import argparse

DEFAULT_REGEX = r'^\[?([^]]+)(]|: )'

def get_input_line(inp_id):
	inp = inputs[inp_id]
	line = inp[0].readline()
	if not line:
		return None
	match = regexes[inp[1]].search(line)
	if not match:
		print("ERROR: unmatched line with regex '{}' in file '{}' with line: {}".format(regexes[inp[1]].pattern, inp[0].name, line), file=sys.stderr)
		exit(1)
	try:
		sortstr = match.group(1)
	except IndexError:
		print("ERROR: missing required capture group in regex '{}'".format(regexes[inp[1]].pattern), file=sys.stderr)
		exit(1)
	if not sortstr:
		print("ERROR: unmatched or empty capture group with regex '{}' in file '{}' with line: {}".format(regexes[inp[1]].pattern, inp[0].name, line), file=sys.stderr)
		exit(1)
	try:
		linedate = dateutil.parser.parse(sortstr)
	except ValueError:
		print("ERROR: got invalid date string '{}' with regex '{}' in file '{}' with line: {}".format(sortstr, regexes[inp[1]].pattern, inp[0].name, line), file=sys.stderr)
		exit(1)
	return (linedate, line.rstrip('\n'), inp_id)

parser = argparse.ArgumentParser(
	usage="%(prog)s [-h] [file [file ...]] [-r regex [file ...]] ...",
	formatter_class=argparse.RawDescriptionHelpFormatter,
	description=(
		"Interleaves lines from multiple log files by timestamp\n"
		"\n"
		"The default regex for extracting timestamps from log file lines is: '" + DEFAULT_REGEX + "'\n"
		),
	epilog=("Examples:\n"
		"  %(prog)s file1 file2\n"
		"  %(prog)s -r '^Date: ([^ ]+)' file1 file2\n"
		"  %(prog)s file1 -r '^Date: ([^ ]+)' file2 -r ',TS=([^,]+)' file3 file4\n"
		))
parser.add_argument('-r', nargs='+', metavar=("regex", "file"), action='append', help="Specify a custom timestamp regex for all following files")
parser.add_argument('file', nargs='*')

args = parser.parse_args()
if not args.r and not args.file:
	parser.print_usage(sys.stderr)
	exit(1)

log_files = {}
regexes = []
try:
	if args.file:
		regexes.append(re.compile(DEFAULT_REGEX))
		log_files[len(regexes)-1] = args.file
	if args.r:
		for group in args.r:
			if len(group) > 1:
				regexes.append(re.compile(group[0]))
				log_files[len(regexes)-1] = group[1:]
except re.error as e:
	print("Error in regex '{}' at position {}: {}".format(e.pattern, e.pos, e.msg), file=sys.stderr)
	exit(1)

inputs = []
try:
	for regex_id, files in log_files.items():
		for file in files:
			inputs.append((open(file, 'r'), regex_id))
except OSError as e:
	print("ERROR: can not open file '{}': {}".format(e.filename, e.strerror), file=sys.stderr)
	exit(1)

lines = [inp for inp in (get_input_line(inp_id) for inp_id in range(len(inputs))) if inp]

lines.sort(reverse=True)
while lines:
	outline = lines.pop()
	print(outline[1])
	newline = get_input_line(outline[2])
	while newline:
		if lines and newline[0] >= lines[-1][0]:
			lines.append(newline)
			lines.sort(reverse=True)
			break
		print(newline[1])
		newline = get_input_line(newline[2])
