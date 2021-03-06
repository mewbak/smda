#!/usr/bin/python

import json
import logging
import os
import traceback
LOGGER = logging.getLogger(__name__)

try:
    import pdbparse
    from pdbparse.undname import undname
except:
    pdbparse = None
    LOGGER.warn("3rd party library pdbparse (use fork @ https://github.com/VPaulV/pdbparse) not installed - won't be able to extract symbols from PDB files where available.")

from .AbstractLabelProvider import AbstractLabelProvider


class DummyOmap(object):
    def remap(self, addr):
        return addr


class PdbSymbolProvider(AbstractLabelProvider):
    """ Minimal resolver for PDB symbols """

    def __init__(self, config):
        self._config = config
        self._base_addr = 0
        # addr:func_name
        self._func_symbols = {}

    def isSymbolProvider(self):
        return True

    def update(self, file_path, binary, base_addr):
        self._base_addr = base_addr
        if not file_path:
            return
        data = ""
        with open(file_path, "rb") as fin:
            data = fin.read()
        if not data[:15] == b"Microsoft C/C++" or pdbparse is None:
            return
        try:
            pdb = pdbparse.parse(file_path)
            self._parseSymbols(pdb)
        except Exception as exc:
            LOGGER.error("Failed parsing \"%s\" with exception type: %s" % (file_path, type(exc)))


    def _parseSymbols(self, pdb):
        try:
            sects = pdb.STREAM_SECT_HDR_ORIG.sections
            omap = pdb.STREAM_OMAP_FROM_SRC
        except AttributeError as e:
            sects = pdb.STREAM_SECT_HDR.sections
            omap = DummyOmap()
        gsyms = pdb.STREAM_GSYM
        for sym in gsyms.globals:
            try:
                off = sym.offset
                if len(sects) < sym.segment:
                    continue
                virt_base = sects[sym.segment - 1].VirtualAddress
                function_address = (self._base_addr + omap.remap(off + virt_base))
                demangled_name = undname(sym.name)
                if sym.symtype == 2:
                    # print("0x%x + 0x%x + 0x%x = 0x%x: %s || %s (type: %d)" % (self._base_addr, off, virt_base, function_address, sym.name, demangled_name, sym.symtype))
                    self._func_symbols[function_address] = demangled_name
            except AttributeError:
                pass

    def getSymbol(self, address):
        return self._func_symbols.get(address, "")

    def getFunctionSymbols(self):
        return self._func_symbols
