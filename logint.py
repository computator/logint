#!/usr/bin/env python
from __future__ import print_function

import re
import os.path
import sys
import datetime
import dateutil.parser
import dateutil.tz
import argparse

DEFAULT_REGEX = r'^\[?([^]]+)(]|: )'

TS_WITH_ZONE = datetime.datetime.now(tz=dateutil.tz.tzlocal())
YEAR_SPLIT = (TS_WITH_ZONE.year % 100) + 10

VALID_COMPONENTS = {'s', 'y', 'm', 'b', 'd', 'H', 'M', 'S', 'f'}

MONTH_MAP = {m.lower(): i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'], start=1)}
_month_from_str_cache = {}
def month_from_str(monthval):
	global _month_from_str_cache
	if not monthval:
		raise ValueError()
	if monthval[:9] in _month_from_str_cache:
		return _month_from_str_cache[monthval[:9]]
	monthstr = monthval.lower()
	try:
		month = next(MONTH_MAP[m] for m in MONTH_MAP if m.startswith(monthstr))
	except StopIteration:
		raise ValueError()
	_month_from_str_cache[monthval[:9]] = month
	return month

def datetime_from_match(match, filename):
	if match.re.groupindex:
		vals = match.groupdict()
		if 's' in vals:
			try:
				return datetime.datetime.fromtimestamp(float(vals['s']), tz=dateutil.tz.tzutc())
			except ValueError:
				print("ERROR: got invalid unix timestamp '{}' with regex '{}' in file '{}' with line: {}".format(vals['s'], match.re.pattern, filename, match.string), file=sys.stderr)
				exit(1)
		else:
			if 'm' in vals:
				try:
					month = int(vals['m'])
				except ValueError:
					print("ERROR: got invalid integer month '{}' with regex '{}' in file '{}' with line: {}".format(vals['m'], match.re.pattern, filename, match.string), file=sys.stderr)
					exit(1)
			else:
				try:
					month = month_from_str(vals['b'])
				except ValueError:
					print("ERROR: got invalid month string '{}' with regex '{}' in file '{}' with line: {}".format(vals['b'], match.re.pattern, filename, match.string), file=sys.stderr)
					exit(1)
			if 'y' in vals:
				try:
					year = int(vals['y'])
				except ValueError:
					print("ERROR: got invalid integer year '{}' with regex '{}' in file '{}' with line: {}".format(vals['y'], match.re.pattern, filename, match.string), file=sys.stderr)
					exit(1)
				if year < 100:
					if year <= YEAR_SPLIT:
						year = year + 2000
					else:
						year = year + 1900
			else:
				year = TS_WITH_ZONE.year
			try:
				return datetime.datetime(
						year,
						month,
						int(vals['d']),
						int(vals['H']) if 'H' in vals else 0,
						int(vals['M']) if 'M' in vals else 0,
						int(vals['S']) if 'S' in vals else 0,
						int(vals['f'].strip().ljust(6, '0')) if 'f' in vals else 0,
						TS_WITH_ZONE.tzinfo
					)
			except ValueError as e:
				print("ERROR: got invalid date values from match '{}' with regex '{}' in file '{}': {}".format(match.group(), match.re.pattern, filename, e), file=sys.stderr)
				exit(1)
	else:
		sortstr = match.group(1)
		if not sortstr:
			print("ERROR: unmatched or empty capture group with regex '{}' in file '{}' with line: {}".format(match.re.pattern, filename, match.string), file=sys.stderr)
			exit(1)
		try:
			return dateutil.parser.parse(sortstr, default=TS_WITH_ZONE)
		except ValueError:
			print("ERROR: got invalid date string '{}' with regex '{}' in file '{}' with line: {}".format(sortstr, match.re.pattern, filename, match.string), file=sys.stderr)
			exit(1)

def get_input_line(inp_id):
	inp = inputs[inp_id]
	line = inp[0].readline()
	if not line:
		return None
	line = line.rstrip('\n')
	match = regexes[inp[1]].search(line)
	if not match:
		print("ERROR: unmatched line with regex '{}' in file '{}' with line: {}".format(regexes[inp[1]].pattern, inp[0].name, line), file=sys.stderr)
		exit(1)
	return (datetime_from_match(match, inp[0].name), line, inp_id)

parser = argparse.ArgumentParser(
	usage="%(prog)s [-h] [file [file ...]] [-r regex [file ...]] ...",
	formatter_class=argparse.RawDescriptionHelpFormatter,
	description=(
		"Interleaves lines from multiple log files by timestamp\n"
		"\n"
		"Regexes can either use named capture groups to extract the various\n"
		"components of a timestamp, or the first capture group to match the\n"
		"entire timestamp (SLOW).\n"
		"\n"
		"Named capture groups are of the format '(?P<name>...)' where 'name' is one\n"
		"of the case sensitive date format specifiers.\n"
		"\n"
		"The default regex for extracting timestamps from log file lines matches\n"
		"the entire timestamp with one capture group: '" + DEFAULT_REGEX + "'\n"
		),
	epilog=(
		"date format specifiers:\n"
		"  's'  Unix Timestamp (supersedes all other values)\n"
		"  'y'  Year as decimal 0000-0999,00-99 " + "(00-99 are converted to 19{:02}-20{:02}) (Default: {:04})".format(YEAR_SPLIT + 1, YEAR_SPLIT, TS_WITH_ZONE.year) + "\n"
		"  'm'  Month as decimal 01-12\n"
		"  'b'  Month as string Jan-Dec,January-December\n"
		"  'd'  Day as decimal 00-31\n"
		"  'H'  Hour as decimal 00-23 (Default: 00)\n"
		"  'M'  Minute as decimal 00-59 (Default: 00)\n"
		"  'S'  Second as decimal 00-59 (Default: 00)\n"
		"  'f'  Fractional second as decimal 0-9,00-99,000-999,000000-999999 (Default: 0)\n"
		"\n"
		"Parameter Examples:\n"
		"  %(prog)s file1 file2\n"
		"  %(prog)s -r '<(.*)>' file1 file2\n"
		"  %(prog)s file1 -r '<(.*)>' file2 -r 'TS=(\\w+)' file3 file4\n"
		"\n"
		"Regex Examples:\n"
		"  Date: Jan 1st 2010 08:01am      '^Date: ([^ ]+)'\n"
		"  Date: 2010-01-01T08:01:01.0001  '^Date: ([^ ]+)'\n"
		"  ...,TS=1262361661,XYZ=...       ',TS=([^,]+)'\n"
		"  [1262361661]                    '\\[(?P<s>[0-9]+())\\]'\n"
		"  [1262361661.0001]               '\\[(?P<s>[0-9]+\\.[0-9]+)\\]'\n"
		"  [01/01/2010]                    '\\[(?P<m>[0-9]+)/(?P<d>[0-9]+)/(?P<y>[0-9]+)\\]'\n"
		"  Jan 01 08:01:01                 '^(?P<b>\\w+) (?P<d>[0-9]+) (?P<H>[0-9]+):(?P<M>[0-9]+):(?P<S>[0-9]+)'\n"
		))
parser.add_argument('-r', nargs='+', metavar=("regex", "file"), action='append', help="Specify a custom timestamp regex for all following files")
parser.add_argument('file', nargs='*')

args = parser.parse_args()
if not args.r and not args.file:
	parser.print_usage(sys.stderr)
	exit(1)
if args.r:
	for group in args.r:
		if len(group) <= 1:
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
			regexes.append(re.compile(group[0]))
			log_files[len(regexes)-1] = group[1:]
except re.error as e:
	print("Error in regex '{}' at position {}: {}".format(e.pattern, e.pos, e.msg), file=sys.stderr)
	exit(1)
for regex in regexes:
	if regex.groupindex:
		if not VALID_COMPONENTS.issuperset(regex.groupindex):
			print("ERROR: unrecognized named capture group '{}' in regex '{}'".format(set(regex.groupindex).difference(VALID_COMPONENTS).pop(), regex.pattern), file=sys.stderr)
			exit(1)
		if 's' in regex.groupindex:
			continue
		if 'd' in regex.groupindex and {'m', 'b'}.intersection(regex.groupindex):
			continue
		print("ERROR: missing required named capture groups in regex '{}'".format(regex.pattern), file=sys.stderr)
		exit(1)
	elif regex.groups < 1:
		print("ERROR: missing required capture group in regex '{}'".format(regex.pattern), file=sys.stderr)
		exit(1)

inputs = []
try:
	for regex_id, files in log_files.items():
		for file in files:
			inputs.append((open(file, 'r'), regex_id))
except (OSError, IOError) as e:
	print("ERROR: can not open file '{}': {}".format(e.filename, e.strerror), file=sys.stderr)
	exit(1)

lines = [inp for inp in (get_input_line(inp_id) for inp_id in range(len(inputs))) if inp]

lines.sort(reverse=True)
while lines:
	outline = lines.pop()
	print(outline[1])
	newline = get_input_line(outline[2])
	while newline:
		if lines and newline[0] > lines[-1][0]:
			lines.append(newline)
			lines.sort(reverse=True)
			break
		print(newline[1])
		newline = get_input_line(newline[2])
