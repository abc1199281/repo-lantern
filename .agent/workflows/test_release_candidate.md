---
description: Test the current Lantern CLI release against the BatchSmith repository
---
1. Initialize Lantern configuration in target repo
// turbo
2. Generate an analysis plan
// turbo
3. Run the analysis (with auto-confirm)
// turbo
4. Verify no authentication errors in output

Command lines:
1. `rm -rf ../batchsmith/.lantern`
2. `poetry run lantern init --repo ../batchsmith`
3. `poetry run lantern plan --repo ../batchsmith`
4. `poetry run lantern run --repo ../batchsmith --yes`
5. `if [ -d ../batchsmith/.lantern/output ]; then ! grep -r "401 Unauthorized" ../batchsmith/.lantern/output; fi`
