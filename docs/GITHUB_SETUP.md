# Repository setup

The project lives at <https://github.com/saxcodez/iox_stats>. These steps publish a local copy there for the first
time (from your Mac). Never put a token or password into a chat, an issue or a commit.

## First push with the GitHub CLI

```bash
brew install gh
gh auth login
```

Choose GitHub.com, HTTPS, and log in in the browser. Then, inside the project folder:

```bash
git init -b main
git add .
git commit -m "Release v0.8.0"
git remote add origin https://github.com/saxcodez/iox_stats.git
git push -u origin main
```

If the repository does not exist yet, `gh repo create saxcodez/iox_stats --public --source . --push` creates it and
pushes in one step (use `--private` to keep it private for now).

## Make it a community project

1. Repository > **Settings > General**: add the description
   "macOS system status in iOS widget style - menu bar, glass widgets, widget gallery" and the topics
   `macos`, `widgets`, `menu-bar`, `system-monitor`, `python`, `swiftui`, `widgetkit`.
2. **Settings > General > Features**: turn on *Issues* (templates are in `.github/ISSUE_TEMPLATE`) and optionally
   *Discussions* for questions and ideas.
3. **Settings > Actions > General**: allow actions, *Workflow permissions*: *Read and write* (the release workflow
   creates GitHub Releases).
4. **Settings > Branches**: optionally protect `main` (require pull requests and passing CI).
5. `LICENSE` (PolyForm Noncommercial 1.0.0) and `CONTRIBUTING.md` are shown by GitHub automatically. GitHub does
   not recognise PolyForm as a standard license and shows "View license" - that is expected.

## Releases

See [RELEASING.md](RELEASING.md). In short: `git tag -a vX.Y.Z -m "IOX Stats vX.Y.Z" && git push origin vX.Y.Z`.
