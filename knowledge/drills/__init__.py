"""Drills: read-only pre-flight checks for dated operations (Round 113).

A drill module answers one question - "will the thing scheduled for <date> actually fire and do
what the vault says it will?" - by checking every piece the operation depends on, against each
other, without writing anything. Each check is PASS, WARN or FAIL; a FAIL exits non-zero.
"""
