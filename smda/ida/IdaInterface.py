import re

from .BackendInterface import BackendInterface

try:
    # we only need these when we are in IDA
    import idautils
    import idc
    import idaapi
except:
    pass

class IdaInterface(BackendInterface):

    def __init__(self):
        self._processor_map = {
            "metapc": "intel"
        }
        self._api_map = {}
        self._import_module_name = ""

    def getArchitecture(self):
        # https://reverseengineering.stackexchange.com/a/11398
        info = idaapi.get_inf_structure()
        procname = info.procName
        if procname in self._processor_map:
            return self._processor_map[procname]
        else:
            raise ValueError("Unsupported Architecture")

    def getBitness(self):
        # https://reverseengineering.stackexchange.com/a/11398
        bits = None
        info = idaapi.get_inf_structure()
        if info.is_64bit():
            bits = 64
        elif info.is_32bit():
            bits = 32
        else:
            bits = 16
        return bits

    def getFunctions(self):
        return sorted([offset for offset in idautils.Functions()])

    def getBlocks(self, function_offset):
        blocks = []
        function_chart = idaapi.FlowChart(idaapi.get_func(function_offset))
        for block in function_chart:
            extracted_block = []
            for instruction in idautils.Heads(block.startEA, block.endEA):
                if idc.isCode(idc.GetFlags(instruction)):
                    extracted_block.append(instruction)
            if extracted_block:
                blocks.append(extracted_block)
        return sorted(blocks)

    def getInstructionBytes(self, offset):
        ins = idautils.DecodeInstruction(offset)
        ins_bytes = idc.get_bytes(offset, ins.size)
        return ins_bytes

    def getCodeInRefs(self, offset):
        return [(ref_from, offset) for ref_from in idautils.CodeRefsTo(offset, True)]

    def getCodeOutRefs(self, offset):
        return [(offset, ref_to) for ref_to in idautils.CodeRefsFrom(offset, True)]

    def getFunctionSymbols(self):
        function_symbols = {}
        function_offsets = self.getFunctions()
        for function_offset in function_offsets:
            function_name = idc.GetFunctionName(function_offset)
            if not re.match("sub_[0-9a-fA-F]+", function_name):
                function_symbols[function_offset] = function_name
        return function_symbols

    def getBaseAddr(self):
        segment_starts = [ea for ea in idautils.Segments()]
        first_segment_start = segment_starts[0]
        # re-align by 0x10000 to reflect typically allocation behaviour for IDA-mapped binaries
        first_segment_start = (first_segment_start / 0x10000) * 0x10000
        return first_segment_start

    def getBinary(self):
        result = b""
        segment_starts = [ea for ea in idautils.Segments()]
        offsets = []
        start_len = 0
        for start in segment_starts:
            end = idc.SegEnd(start)
            result += idc.get_bytes(start, end - start)
            offsets.append((start, start_len, len(result)))
            start_len = len(result)
        return result

    def getApiMap(self):
        self._api_map = {}
        num_imports = idaapi.get_import_module_qty()
        for i in range(0, num_imports):
            self._import_module_name = idaapi.get_import_module_name(i)
            idaapi.enum_import_names(i, self._cbEnumImports)
        return self._api_map

    def _cbEnumImports(self, addr, name, ordinal):
        # potentially use: idc.Name(addr)
        self._api_map[addr] = self._import_module_name + "!" + name
        return True
