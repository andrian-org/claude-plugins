# Project Rules

> Short, actionable rules and conventions for this project. Loaded automatically by /aif-implement.

## Rules

- Before a validator encodes a DGF runtime behaviour, read the runtime code path that implements it (converter, manager or loader); a schema or XSD is no evidence of what the runtime accepts
- Resolve DGF file references with an exact-case directory lookup (os.scandir), never Path.exists(); APFS and NTFS match regardless of case, Linux does not
- Settle every error in DGF's samples with a validator fix or an EXCEPTION line citing the runtime code path in tools/known-good-exceptions.txt; never add an exception to make a validator gap pass
- A skill that STOPs on a script's exit code must be walked through its own worked example against that script
- Tests that assert an exact finding list must pass under an interpreter without lxml and jsonschema
- When a thread feeds a subprocess's stdin, kill the process before joining the thread if you stop reading its output
- Build every dgf-gate-result block through scripts/lib/gate_result.py; never assemble or render one by hand in a script or skill (ADR 0020)
