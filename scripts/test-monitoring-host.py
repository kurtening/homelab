#!/usr/bin/env python3
"""Synthetic preflight fixtures; no privileged operations or live journals."""
import hashlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
loader=importlib.machinery.SourceFileLoader('hostcheck',str(ROOT/'host/krof-desktop/monitoring/check-monitoring-host'))
spec=importlib.util.spec_from_loader(loader.name,loader)
h=importlib.util.module_from_spec(spec);loader.exec_module(h)

class Tests(unittest.TestCase):
    def test_expected_hash_matches_reviewed_source(self):
        self.assertEqual(h.EXPECTED_COLLECTOR,hashlib.sha256((ROOT/'host/krof-desktop/monitoring/homelab-metrics').read_bytes()).hexdigest())

    def test_exporter_view_freshness_and_mounts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'homelab.prom'
            descriptor=os.open(d,os.O_RDONLY|os.O_DIRECTORY)
            try:
                with patch.object(h.os,'setgroups'),patch.object(h.os,'setgid') as gid,patch.object(h.os,'setuid') as uid:
                    for age,mount,passed in [(0,1,True),(400,1,False),(0,0,False)]:
                        p.write_text('homelab_collector_last_success_timestamp_seconds '+str(time.time()-age)+'\n'
                                     'homelab_storage_mount_valid{role="data"} '+str(mount)+'\n'
                                     'homelab_storage_mount_valid{role="backup"} 1\n')
                        if passed:h.exporter_check(descriptor)
                        else:
                            with self.assertRaises(ValueError):h.exporter_check(descriptor)
                    gid.assert_called_with(65534);uid.assert_called_with(65534)
            finally:os.close(descriptor)

    def test_journal_header_only_and_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fixture.journal';p.write_bytes(b'LPKSHHRH'+b'not read as records')
            self.assertTrue(h.readable_header(p));self.assertFalse(h.readable_header(Path(d)/'absent'))
            with patch.object(h.os,'setgroups') as groups,patch.object(h.os,'setgid'),patch.object(h.os,'setuid') as uid:
                h.journal_check([str(p)]);groups.assert_called_with([101]);uid.assert_called_with(473)

if __name__=='__main__':unittest.main()
