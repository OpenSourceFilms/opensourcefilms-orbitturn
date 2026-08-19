# Contributing

This is active production R&D tooling, not a general-purpose framework —
see the README's Status section before assuming a change fits every use
case.

The most useful contributions right now:

- Wiring `custom_nodes/osf_h3_hybrid/` and `custom_nodes/osf_h3_maxq/` into
  a saved, end-to-end working copy of `workflows/OrbitTurn_H3_comparison_workflow.json`
  (see the README's Status section — this genuinely doesn't exist yet as a
  saved file).
- Filling in the "Not yet verified" rows in `THIRD_PARTY_LICENSES.md` with
  actual license text, not assumptions.
- Reports of the runtime patch in `osf_h3_hybrid` (`_install_mixed_h3_payload_patch`)
  breaking against a newer ComfyUI-core MiniMax H3 implementation, since it
  patches a specific version's internals and will need updating as that
  code changes upstream.

Keep pull requests scoped to this repository's actual OSF-authored code
(`custom_nodes/`, docs). Third-party dependencies belong in their own
upstream projects, not vendored in here.
