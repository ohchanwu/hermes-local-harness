# Concurrency

Five implementation profiles may run concurrently: the three Flash and two Luna lanes initially. `reviewer-sol` stays dispatchable outside that budget. Keep native `kanban.max_in_progress` unset and `kanban.max_in_progress_per_profile` at 1. Raise capacity only after measured saturation, queue delay, reviewer latency, provider limits, cost, and repository contention support a separately approved change.
