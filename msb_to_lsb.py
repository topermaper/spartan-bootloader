import sys

m2l = lambda n: bytes([int('{:08b}'.format(n)[::-1], 2)])

if __name__ == '__main__':
	usage_help = """Error: wrong parameter count.
Usage:
	{0} <LOADER_FILE.LDR>"""

	# Check if enough parameters have been passed
	if len(sys.argv) < 2:
		sys.exit(usage_help.format(sys.argv[0]))
	elif not sys.argv[1].endswith(".ldr"):
		sys.exit("Error: loader file must have .ldr extension.")

	# Try opening the file
	try:
		loader = open(sys.argv[1], 'rb')
	except:
		sys.exit("Error: could not open loader file: {0}\output.txt".format(sys.argv[1]))

	source = loader.read()
	loader.close()

	output = bytes()

	for b in source:
		output += m2l(b)

	bin_filename = "{0}.dat".format(sys.argv[1].replace('.ldr', ''))
	bin_file = open(bin_filename, 'wb')
	bin_file.write(output)
	bin_file.close()

	print("Success: {0}".format(bin_filename))
