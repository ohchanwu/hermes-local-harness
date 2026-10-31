# Card contracts that extend scripts/apply_changeset.py

Write these exceptions into the card body before dispatch. A worker blocks on each one that is missing, and two blocks for the same kind of reason send the card to triage.

A new AnkiConnect action or a new change set entry type cannot keep "existing tests pass unchanged". `tests/test_apply_changeset.py` holds its own copies of the safety lists and the example file:
- `SPEC_WRITE_ACTIONS` (about line 774) must include every name in `WRITE_ACTIONS`. Allow adding the new action to it, and nothing else in `ANKICONNECT_ACTIONS`, `SPEC_READ_ACTIONS`, or `SPEC_BACKUP_ACTIONS`. Also require a new test that limits the parameters of the new action.
- `tests/fixtures/example_changeset.json` is the "Complete example" of `docs/CHANGESET_FORMAT.md` and holds one entry of every type. Several tests loop over `ENTRY_TYPES` with this fixture. Put the fixture in the allowed files, and keep the new top-level key optional through a separate tuple, so that `test_every_key_is_required` still passes.
- `test_action_order_reads_then_exports_then_writes_then_reads` asserts the exact list of write actions. The new action has to be inserted there in apply order.
- The backup tests (`test_note_with_cards_in_several_decks_backs_up_every_deck`, `test_decks_with_the_same_safe_name_get_distinct_files`) clear the other entry lists by name. A new entry type must be added to those lists.
- Additions to the `StubAnki` server inside the test file (new `do_<action>` methods, new card fields) count as test infrastructure.

Write one general rule into the card: an existing test may change only by adding the new type or action to a list that the test enumerates, orders, or clears. No assertion may be removed or weakened. Every such change is listed in the handoff.

To set or clear a card flag, the installed AnkiConnect uses `setSpecificValueOfCard` with `{card, keys:["flags"], newValues:[0..7]}`. It returns `[true]` on success and `[[false, msg]]` on failure. `cardsInfo` returns `flags`.
