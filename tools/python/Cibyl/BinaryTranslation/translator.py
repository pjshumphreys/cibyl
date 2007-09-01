######################################################################
##
## Copyright (C) 2006,  Simon Kagstrom
##
## Filename:      translator.py
## Author:        Simon Kagstrom <ska@bth.se>
## Description:   Describes a MIPS binary
##
## $Id: translator.py 14248 2007-03-14 17:13:31Z ska $
##
######################################################################
import StringIO, re, sys, struct, bisect, tempfile, os, subprocess, copy
from sets import Set

if __name__ == "__main__":
    sys.path.append('%s/../../' % sys.path[0])

from Cibyl.BinaryTranslation import bytecode, register, function, codeblock, javaclass
from Cibyl.BinaryTranslation.Mips.instruction import Instruction, newInstruction, Syscall, SyscallRegisterArgument
from Cibyl.BinaryTranslation.Mips import mips, optimizer, javamethod

from Cibyl import config

import Cibyl.SyscallHandling.function, Cibyl.elf


def getSyscallStrings(data):
    """Split the .cibylstrtab section into address : string mappings
    (and the other way around"""
    addressesToName = {}
    strs = data.split("\0")

    cur = 0
    for s in strs:
	addressesToName[cur] = s
	cur = cur + len(s) + 1
    return addressesToName

class JasminProcess:
    def __init__(self, name, data):
        self.fd, self.filename = tempfile.mkstemp(prefix = name + "_", suffix = ".j", dir = config.outDirectory)
        # Write the data to the tempfile
        os.write(self.fd, data)
        os.close(self.fd)

        # Fork jasmin
        self.process = subprocess.Popen([ config.jasmin, "-d " + config.outDirectory + " " + self.filename ])

    def wait(self):
        "Wait for the process to complete and clean up after it"
        try:
            os.waitpid(self.process.pid, 0)
        except:
            # Already terminated
            pass
        if not config.saveTemps:
            os.unlink(self.filename)


class Controller(codeblock.CodeBlock):
    def __init__(self, filename, syscallDirectories, onlyReadSyscalls=False):
	self.filename = filename
	self.syscallDirectories = syscallDirectories
	self.tracing = config.tracing
	self.labels = {}
	self.instructions = []
	self.instructionsByAddress = {}
	self.syscalls = {}
	self.usedSyscalls = {}
	self.compileFunctions = True
        self.prunedRanges = []
        self.jasminProcesses = []

	self.optimizer = optimizer.Optimizer()
	self.registerHandler = register.RegisterHandler(self, bytecode.ByteCodeGenerator(self))
	self.elf = Cibyl.elf.Elf(self.filename)

	self.addressesToName = getSyscallStrings(self.elf.getSectionContents(".cibylstrtab"))

	# Read everything
	allFunctions = Cibyl.SyscallHandling.function.functionsFromHeaderDirectories(syscallDirectories)
	for fn in allFunctions:
	    self.addSyscall(fn)
	self.readBinary()

	# Fixup the jump destinations and other stuff with the instructions
        for insn in self.instructions:
            insn.fixup()
            self.instructionsByAddress[insn.address] = insn
            if insn.delayed:
                assert(not self.instructionsByAddress.has_key(insn.delayed.address))
                self.instructionsByAddress[insn.delayed.address] = insn.delayed
                insn.delayed.fixup()
            if insn.prefix:
                assert(not self.instructionsByAddress.has_key(insn.prefix.address))
                self.instructionsByAddress[insn.prefix.address] = insn.prefix
                insn.prefix.fixup()
            if insn.address in self.labels:
                insn.isBranchDestination = True

	# Arrange instructions into functions
	self.functions = []
	for sym in self.elf.getSymbolsByType("tW"):
            if self.isPruned(sym.address) >= 0:
                continue
	    # Add a label for this address and create a new function
	    self.addLabel(sym.address, inJumpTab = True, name = sym.name, isFunction = True)
	    insns, labels = self.splitByAddresses(sym.address, sym.address + sym.size)

	    # Maybe trace this function
	    useTracing = self.tracing
	    if config.traceFunctions:
		useTracing = sym.name in config.traceFunctions

	    fn = function.Function(self, sym.name, insns, labels, useTracing)
	    self.functions.append(fn)

	self.functions.sort()
	javaMethods = []

        colocateFunctions = []
        otherFunctions = []
        for fn in self.functions:
            if fn.name in config.colocateFunctions:
                colocateFunctions.append(fn)
            else:
                otherFunctions.append(fn)

        # Insert java methods (colocated and normal)
        if colocateFunctions != []:
            javaMethods.append(javamethod.JavaMethod(self, colocateFunctions))

	for fn in otherFunctions:
	    javaMethods.append(javamethod.JavaMethod(self, [fn]))
	self.jumptab = javamethod.GlobalJumptabMethod(self, colocateFunctions + otherFunctions)
	javaMethods.append(self.jumptab)

        self.javaClasses = self.splitMethodsInClasses(javaMethods)

    def getGlobalCallTableMethod(self):
        return self.jumptab

    def getOptimizer(self):
	"Return the optimizer"
	return self.optimizer

    def getInstruction(self, address):
        return self.instructionsByAddress[address]

    def markSyscallUsed(self, name):
	"Mark syscall nr as used"
	self.usedSyscalls[name] = True

    def markSyscallUnsed(self, name):
	"Mark syscall nr as used"
	self.usedSyscalls[name] = True

    def addSyscall(self, func):
	"Add a syscall for a given function"
	self.syscalls[func.name] = func

    def hasSyscall(self, address):
	"Return the syscall on the address @a address"
	name = self.addressesToName[address]
	return self.syscalls[name]

    def usesSyscall(self, name):
	"Check if a named syscall is actually used"
	return self.usedSyscalls.has_key(name)

    def lookupJavaMethod(self, address):
	"Return the java method for a given address"
        for c in self.javaClasses:
            out = c.lookupJavaMethod(address)
            if out:
                return out
        return None

    def lookupFunction(self, address):
	"Return the function for a given address"
        for c in self.javaClasses:
            out = c.lookupFunction(address)
            if out:
                return out
        return None

    def splitMethodsBySize(self, javaMethods):
        "Split methods into classes by the size of the classes"
        size = 0
        out = []
        curMethods = []
        name = "Cibyl"
        for method in javaMethods:
            size = size + method.getSize()
            curMethods.append(method)
            if size > 12000:
                jc = javaclass.JavaClass(self, name)
                for m in curMethods:
                    jc.addMethod(m)
                out.append(jc)
                curMethods = []
                size = 0
                name = "Cibyl%d" % len(out)
        if curMethods != []:
            jc = javaclass.JavaClass(self, name)
            for m in curMethods:
                jc.addMethod(m)
            out.append(jc) # Place the smallest first
        return out

    def splitMethodsInClasses(self, javaMethods):
        methodsToSplit = copy.copy(javaMethods)
        addToPrimary = []

        # Some should always be in the first class
        for method in methodsToSplit:
            if method == self.jumptab or method.name == "start":
                addToPrimary.append(method)
                del methodsToSplit[ methodsToSplit.index(method) ]
        # Split the methods
        out = self.splitMethodsBySize(methodsToSplit)
        primary = out[0]

        # ... And add to first
        for method in addToPrimary:
            primary.addMethod(method)
        return out

    def addAlignedSection(self, out, sectionName, alignment):
	section = self.elf.getSectionContents(sectionName)
	addr = len(out)
	pad = 0
	if (addr & (alignment-1)):
	    pad = ((-addr) & (alignment-1))
	out = out + "\0" * pad
	out = out + section
	return out

    def addPrunedRange(self, start, end):
        self.prunedRanges.append( start )
        self.prunedRanges.append( end - 1 )

    def isPruned(self, address):
        "Check if address is pruned. Returns the address of the next unpruned instruction"
        for r in range(0, len(self.prunedRanges), 2):
            if address in (self.prunedRanges[r], self.prunedRanges[r+1]):
                return self.prunedRanges[r+1]
        return -1

    def writeDataFile(self, filename):
	"Output the raw .data/.rodata file"
	sections = self.addAlignedSection("", ".data", 16)
	sections = self.addAlignedSection(sections, ".rodata", 16)
	sections = self.addAlignedSection(sections, ".ctors", 4)
	sections = self.addAlignedSection(sections, ".dtors", 4)

	# Write the data outfile
	out = open(filename, "w")
	out.write(sections)
	out.close()


    def forkJasmin(self, name, data):
        self.jasminProcesses.append(JasminProcess(name, data))

    # Based on Instruction.java from the Topsy OS by
    # George Fankhauser <gfa@acm.org>
    def readBinary(self):
	"Parse the binary file and create the instructions"

	baseAddress = self.elf.getEntryPoint()
	text = self.elf.getSectionContents(".text")
	rodata = self.elf.getSectionContents(".rodata") + self.elf.getSectionContents(".ctors") + self.elf.getSectionContents(".dtors")

	# Add all .rodata refs to the .text segment to the lookup table
	for i in range(0, len(rodata), 4):
	    data = rodata[i:i+4]
	    word = struct.unpack(">L", data)[0]

	    if word >= baseAddress and word < baseAddress + len(text):
		self.addLabel(word, True)

        if config.pruneUnusedFunctions:
            for sym in self.elf.getSymbolsByType("tW"):
                # If this function is unused, remove all references to it
                if not self.elf.getRelocation(sym.name) and not sym.type in "t" and sym.address != self.elf.getEntryPoint():
                    self.addPrunedRange( sym.address, sym.address + sym.size )
                    if config.verbose: print "Pruning ", sym.name, "%x..%x" % (sym.address, sym.address+sym.size)
        self.prunedRanges.sort()

	# Parse the instructions
	i = 0
	delaySlot = None
	while i < len(text):
	    data = text[i:i+4]
	    word = struct.unpack(">L", data)[0]

	    address = i + baseAddress

            pruned = self.isPruned(address)
            if pruned > 0:
                i = pruned - baseAddress + 1
                continue

	    extra = 0
	    rs = (word >> 21) & 0x1f
	    rt = (word >> 16) & 0x1f
	    rd = (word >> 11) & 0x1f
	    opEntry = mips.opTable[(word >> 26) & 0x3f]
	    opCode = opEntry[mips.OPCODE]
	    format = mips.SPECIAL

	    # The special encodings are handled here
	    if (word >> 16) == 0xfefe or (word >> 24) == 0xff:
		if (word >> 24) == 0xff:    # Syscall
		    extra = word & 0x00ffffff
		    insn = Syscall(self, address, mips.CIBYL_SYSCALL, opCode, 0,0,0, extra)
                    self.markSyscallUsed( self.addressesToName[insn.extra] )
		elif (word >> 16) == 0xfefe:  # Register-parameter
		    extra = word & 0xffff
		    insn = SyscallRegisterArgument(self, address, mips.CIBYL_REGISTER_ARGUMENT, opCode, 0,0,0, extra)
		else:
		    raise Exception("Unknown special encoding %x" % long(word))
		self.addInstruction(insn)
		i = i + 4
		continue

	    if opEntry[mips.FORMAT] == mips.IFMT:
		format = mips.IFMT
		extra = word & 0xffff
		# Negative?
		if opCode not in mips.ifmtZeroExtend and extra & 0x8000 == 0x8000:
		    extra = (-1 & ~0xffff) | extra

	    elif opEntry[mips.FORMAT] == mips.RFMT:
		format = mips.RFMT
		extra = (word >> 6) & 0x1f
	    else: # JFMT
		format = mips.JFMT
		extra = word & 0x03ffffff

	    if opCode == mips.SPECIAL:
		opCode = mips.specialTable[word & 0x3f]
	    elif opCode == mips.BCOND:
		x = word & 0x1f0000
		if x == 0:
		    opCode = mips.OP_BLTZ
		elif x == 0x10000:
		    opCode = mips.OP_BGEZ
		elif x == 0x100000:
		    opCode = mips.OP_BLTZAL
		elif x == 0x110000:
		    opCode = mips.OP_BGEZAL
		else:
		    opCode = mips.OP_UNIMP

            insn = newInstruction(opCode)(self, address, format, opCode, rd, rs, rt, extra)
            # If the last instruction has a delay slot, add this to
            # it, otherwise add it to the lits of instructions
            if delaySlot:
                delaySlot.addDelayedInstruction(insn)
                delaySlot = None
            else:
                self.addInstruction(insn)
            if insn.opCode in mips.delaySlotInstructions:
                delaySlot = insn
	    i = i + 4

    def compile(self):
	"Recompile the binary"
        for c in self.javaClasses:
            c.fixup()

        for c in self.javaClasses:
            # Finally create the outfile and write to it
            self.outfile = StringIO.StringIO()
            c.compile()
            self.outfile.flush()
            self.forkJasmin(c.getName(), self.outfile.getvalue())
            self.outfile.close()

        # Wait for the jasmin(s) to terminate and cleanup after them
        for p in self.jasminProcesses:
            p.wait()

        self.writeDataFile(config.outDirectory + "/" + config.dataOutFilename)

    def emit(self, what):
	"Emit instructions"
	self.outfile.write(what + "\n")


if __name__ == "__main__":
    """This example should fork two jasmin processes and compile those
    to TstA.class and TstB.class and leave no temporary files behind"""
    d1 = ".class public TstA\n.super java/lang/Object\n"
    d2 = ".class public TstB\n.super java/lang/Object\n"

    procs = [ JasminProcess("TstA", d1), JasminProcess("TstB", d2) ]
    for p in procs:
        p.wait()
