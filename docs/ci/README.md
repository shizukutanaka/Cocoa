# CI workflow (owner action required)

`ci.yml` here is a ready-to-use GitHub Actions workflow. It lives in `docs/ci/`
rather than `.github/workflows/` because the automation token used to develop
this branch is refused by GitHub with:

```
refusing to allow a GitHub App to create or update workflow
`.github/workflows/ci.yml` without `workflows` permission
```

That is a hard permission boundary, not a design choice — the file cannot be
pushed into `.github/workflows/` from this session by any means.

## To enable it

```bash
mkdir -p .github/workflows
git mv docs/ci/ci.yml .github/workflows/ci.yml
git commit -m "ci: enable backend+frontend workflow"
git push
```

## What it runs

Exactly the two commands this project uses as its defence line (see
`HANDOFF_INSTRUCTIONS.md` §3), so green CI means the same thing as a clean
local run:

- **backend** — `python -m unittest` over the four core suites (~923 tests)
- **frontend** — `npm ci && npm run build && npm run lint && npm test`

The full `unittest discover` sweep is deliberately not used: it reports a small
number of pre-existing failures caused purely by optional packages missing in
the environment (`pytest`, `_cffi_backend`), which would make CI red for
reasons unrelated to any change.
