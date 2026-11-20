# Contributing

Thanks for helping. The most useful contributions are false positives and missing providers found on real sites.

1. Fork, then `pip install -e ".[test]"`.
2. Add a fixture under `tests/fixtures/` (a trimmed copy of the relevant markup is enough; remove ids, tokens and personal data) and a test that fails before your change.
3. Run `python -m pytest`. Tests must pass offline and must not use the live network.
4. Keep the library dependency-free (standard library only) and compatible with Python 3.9.
5. New widget signatures go in `src/contactchannels/signatures.py`. Match the host the script loads from or the global object its documented snippet creates, never a plain-text mention.

Please open an issue first for larger changes.
