The script output above lists findings for one Kanban board. The header line `Board <board> check for <profile>:` names that board. Work only on that board and on its repositories as listed in your skill. Do not read or change any other board or repository.

If the output is a single line starting with `Board check error:`, the check itself failed. Do not change anything; report the error line in your final report.

Each finding line has the form `<KIND> <card id> <status> <assignee or -> <title>`. For each finding:

1. Run kanban_show for the card on that board first. The owner's chat session may already have acted on the card. If the finding no longer holds (for example, the card now has a notify+wake subscription, the candidate commit is already on the target branch, or the card has moved out of `blocked` or `review`), do nothing for that finding.
2. NO-WAKE-SUBSCRIPTION: add the missing subscription with the `notify-subscribe` command given in your orchestrator skill, with delivery mode `notify+wake` and your own profile as the notifier profile.
3. APPROVED-NOT-INTEGRATED: the line ends with `commit <candidate>`. Follow the integration steps of your orchestrator skill for that candidate. Merge only with `git merge --ff-only`. If a fast-forward is not possible, or the line ends with `(commit not found)`, do not integrate; report the card and the reason.
4. STALE-BLOCKED and STALE-REVIEW: take the next step that your orchestrator skill allows for the card. If the skill allows no step, report what the card is waiting for and on whom.

Never push, never deploy, and never ask the owner about anything that your orchestrator skill says not to ask about.

End with a report of at most 5 lines. Name the cards you acted on and what you did, and the cards that still wait and on whom.
