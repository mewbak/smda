import datetime

from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_MODE_64

from .IdaInterface import IdaInterface
from smda.DisassemblyResult import DisassemblyResult

class IdaExporter(object):

    def __init__(self, config, bitness=None):
        self.config = config
        self.ida_interface = IdaInterface()
        self.bitness = bitness if bitness else self.ida_interface.getBitness()
        self.capstone = None
        self._file_path = ""
        self.disassembly = DisassemblyResult()
        self._initCapstone()

    def _initCapstone(self):
        self.capstone = Cs(CS_ARCH_X86, CS_MODE_32)
        if self.bitness == 64:
            self.capstone = Cs(CS_ARCH_X86, CS_MODE_64)

    def setFilePath(self, file_path):
        self._file_path = file_path

    def _convertIdaInsToSmda(self, offset, instruction_bytes):
        cache = [i for i in self.capstone.disasm(instruction_bytes, offset)]
        if cache:
            smda_ins = (cache[0].address, cache[0].size, cache[0].mnemonic, cache[0].op_str, cache[0].bytes)
        else:
            # record error and emit placeholder instruction
            bytes_as_hex = "".join(["%02x" % c for c in bytearray(instruction_bytes)])
            print("missing capstone disassembly output at 0x%x (%s)" % (offset, bytes_as_hex))
            self.disassembly.errors[offset] = {
                "type": "capstone disassembly failure",
                "instruction_bytes": bytes_as_hex
            }
            smda_ins = (offset, len(instruction_bytes), "error", "error", bytearray(instruction_bytes))
        return smda_ins

    def analyzeBuffer(self, binary=None, base_addr=None, bitness=None, cbAnalysisTimeout=None):
        """ instead of performing a full analysis, simply collect all data from IDA and convert it into a report """
        self.disassembly.analysis_start_ts = datetime.datetime.utcnow()
        self.disassembly.base_addr = base_addr if base_addr else self.ida_interface.getBaseAddr()
        self.disassembly.binary = binary if binary else self.ida_interface.getBinary()
        self.disassembly.architecture = self.ida_interface.getArchitecture()
        self.disassembly.bitness = bitness if bitness else self.bitness
        self.disassembly.function_symbols = self.ida_interface.getFunctionSymbols()
        api_map = self.ida_interface.getApiMap()
        for function_offset in self.ida_interface.getFunctions():
            converted_function = []
            for block in self.ida_interface.getBlocks(function_offset):
                converted_block = []
                for instruction_offset in block:
                    instruction_bytes = self.ida_interface.getInstructionBytes(instruction_offset)
                    smda_instruction = self._convertIdaInsToSmda(instruction_offset, instruction_bytes)
                    converted_block.append(smda_instruction)
                    self.disassembly.instructions[smda_instruction[0]] = (smda_instruction[2], smda_instruction[1])
                    in_refs = self.ida_interface.getCodeInRefs(smda_instruction[0])
                    for in_ref in in_refs:
                        self.disassembly.addCodeRefs(in_ref[0], in_ref[1])
                    out_refs = self.ida_interface.getCodeOutRefs(smda_instruction[0])
                    for out_ref in out_refs:
                        self.disassembly.addCodeRefs(out_ref[0], out_ref[1])
                        if out_ref[1] in api_map:
                            self.disassembly.addr_to_api[instruction_offset] = api_map[out_ref[1]]
                converted_function.append(converted_block)
            self.disassembly.functions[function_offset] = converted_function
            if self.disassembly.isRecursiveFunction(function_offset):
                self.disassembly.recursive_functions.add(function_offset)
            if self.disassembly.isLeafFunction(function_offset):
                self.disassembly.leaf_functions.add(function_offset)
        self.disassembly.analysis_end_ts = datetime.datetime.utcnow()
        return self.disassembly
