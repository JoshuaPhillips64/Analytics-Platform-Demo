# CI / GitHub setup

CI (`.github/workflows/ci.yml`) runs on every PR/push to `main`: it spins a
Postgres **service container**, loads a committed raw-data **fixture**
(`.github/ci/seed_raw_fixture.sql` — KO + economic, generated from real data so
it passes every test), then runs `dbt deps`, `sqlfluff lint`, `dbt parse`, and
`dbt seed && dbt build` (every model **and** every test). A failing model/test
makes `dbt build` non-zero, which fails the check and blocks the merge.

This whole flow was validated locally against a throwaway Postgres (PASS=99).

## One-time steps (manual — needs your GitHub account)

1. **Create the repo and push** (public repo → free Actions minutes, golden rule #6):
   ```bash
   gh repo create equities-analytics-platform --public --source . --remote origin --push
   # or: create the repo in the UI, then:
   #   git remote add origin git@github.com:<you>/equities-analytics-platform.git
   #   git push -u origin main
   ```
   (Current local branch is `master`; push it as `main`:
   `git branch -M main && git push -u origin main`.)

2. **Confirm CI is green:** open the Actions tab; the `CI` workflow should pass on
   the initial push.

3. **Enable branch protection** on `main` (Settings → Branches → add rule), or:
   ```bash
   gh api -X PUT repos/<you>/equities-analytics-platform/branches/main/protection \
     -F required_status_checks.strict=true \
     -F 'required_status_checks.contexts[]=dbt' \
     -F enforce_admins=true \
     -F required_pull_request_reviews.required_approving_review_count=0 \
     -F restrictions=
   ```

4. **Verify the gate:** open a PR that breaks a model (e.g. change a `stg_` model
   to violate a test) and confirm CI goes red and the merge is blocked. Revert.

No secrets are needed in CI — it uses the ephemeral Postgres + the committed
fixture, never RDS or Alpha Vantage.
