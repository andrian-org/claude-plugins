# Project Rules

> Short, actionable rules and conventions for this project. Loaded automatically by /aif-implement.

## Rules

- Before a validator encodes a DGF runtime behaviour, read the runtime code path that implements it (converter, manager or loader); a schema or XSD is no evidence of what the runtime accepts
- Resolve DGF file references with an exact-case directory lookup (os.scandir), never Path.exists(); APFS and NTFS match regardless of case, Linux does not
- Settle every error in DGF's samples with a validator fix or an EXCEPTION line citing the runtime code path in tools/known-good-exceptions.txt; never add an exception to make a validator gap pass
