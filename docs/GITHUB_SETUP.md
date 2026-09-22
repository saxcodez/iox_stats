# GitHub einbinden (privates Repository)

Ein privates Repo ist für dieses Projekt kein Problem - es wird genau wie ein öffentliches benutzt,
nur mit Anmeldung. Der einfachste Weg ist, den Code **einmal von deinem Mac aus** hochzuladen.

## Variante A: GitHub CLI (empfohlen, am einfachsten)

```bash
brew install gh
gh auth login                     # GitHub.com -> HTTPS -> im Browser anmelden

unzip IOX_Stats_v0.1.0.zip
cd IOX_Stats_v0.1.0

git init -b main
git add .
git commit -m "Release v0.1.0"
git remote add origin https://github.com/DEIN-USER/DEIN-REPO.git
git push -u origin main

git tag -a v0.1.0 -m "IOX Stats v0.1.0"
git push origin v0.1.0            # startet den Release-Workflow
```

`gh auth login` speichert die Anmeldung; danach funktionieren `git push`/`git pull` auch für private Repos.

## Variante B: SSH-Key

```bash
ssh-keygen -t ed25519 -C "santinobusch@yahoo.de"
pbcopy < ~/.ssh/id_ed25519.pub    # Key in die Zwischenablage
```

GitHub -> Settings -> SSH and GPG keys -> New SSH key -> einfügen. Dann:

```bash
git remote add origin git@github.com:DEIN-USER/DEIN-REPO.git
```

## Variante C: Claude direkt mit dem Repo arbeiten lassen

Wenn du in Claude Code im Web die Claude-GitHub-App für dein Konto/dieses Repo installierst und eine
neue Session mit dem Repo startest, wird das (auch private) Repo in die Session geklont und ich kann
Branches pushen bzw. Pull Requests öffnen. Dafür brauche ich nie ein Token im Chat.

**Bitte niemals ein Personal Access Token oder Passwort in den Chat schreiben.**
Falls du ein Token brauchst (z. B. für Skripte): GitHub -> Settings -> Developer settings ->
Fine-grained tokens -> nur dieses eine Repo, nur "Contents: Read and write".

## Danach

1. Repo -> Settings -> Actions -> General: Workflows erlauben (Read and write permissions für den Release-Workflow).
2. In `CHANGELOG.md` die Platzhalter `OWNER` in den Vergleichslinks durch deinen GitHub-Namen ersetzen
   (`OWNER/IOX_Stats` -> `DEIN-USER/DEIN-REPO`).
3. Für neue Releases siehe [RELEASING.md](RELEASING.md).
