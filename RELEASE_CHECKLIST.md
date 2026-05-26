# Release Checklist

Run this before tagging any release. It exists because the maintainer's own
HA install pre-bootstraps everything — cold-install bugs are invisible
without spinning up a clean instance. Two install-time bugs (#1 BoredFog
config_flow crash, #2 chubban-lgtm panel-deadlock) shipped to users before
this ritual existed. Don't ship a third.

The whole pass should take 10–15 minutes. Most of that is HA starting up
and clicking through the wizard.

---

## 1. Pre-tag smoke pass (the cold install)

### 1a. Fresh container

```bash
docker compose down       # if a previous test container is running
rm -rf .test-config/      # nuke any prior HA state for true cold install
docker compose up         # foreground so logs are visible
```

Wait until you see `Home Assistant initialized in X seconds`. Open
<http://localhost:8123> in a private/incognito window so cached UI state
from your real HA doesn't bleed in.

### 1b. HA onboarding (~2 min)

- Create a fresh owner account (any throwaway credentials)
- Skip location / detect devices / etc — get to the dashboard ASAP

### 1c. Install the integration

- **Settings → Devices & Services → Add Integration → "Eufy Vacuum Manager"**
- Setup wizard appears
  - ☐ **No 500 error** when the wizard opens (regression check for #1)
  - ☐ **No `{context}` translation warning** in the wizard description
  - ☐ The "Vacuum" picker is present and shows a dropdown
- Submit **without** picking a vacuum (the dropdown will be empty anyway —
  no upstream eufy-clean is mounted in the test container)
- ☐ "Success" screen appears

### 1d. Verify the fallback panel

- ☐ A sidebar entry **"Eufy Vacuum"** appears (regression check for #2)
- ☐ Clicking it opens a "setup needed" placeholder card
- ☐ The placeholder shows step-by-step instructions pointing back at
  Settings → Devices & Services → Configure
- ☐ No JS errors in the browser console
- ☐ The placeholder renders correctly at both desktop and mobile
  viewport widths (resize the browser to ~390px width to check)

### 1e. Walk the Options-flow recovery path

- **Settings → Devices & Services → Eufy Vacuum Manager → Configure**
- ☐ The form shows both **Vacuum** picker and **Notes**
- ☐ Without an actual vacuum entity available in this test instance, leave
  Vacuum blank, edit Notes, submit
- ☐ Integration reloads cleanly (check logs for `INFO` reload line, no
  ERROR or WARNING new lines)
- ☐ Sidebar still shows "Eufy Vacuum"; clicking it still shows the
  placeholder

### 1f. Restart HA

- Developer Tools → Restart Home Assistant
- After reboot:
  - ☐ Integration loads with no errors in the logs
  - ☐ Sidebar entry still present
  - ☐ Placeholder panel still renders

### 1g. Stop the container

```bash
docker compose down
```

Keep `.test-config/` between runs unless you intentionally want a
brand-new HA. Wipe it before any release-blocker test.

---

## 2. Version bump

```bash
# In custom_components/eufy_vacuum/manifest.json:
"version": "0.9.X"   # bump per semver — patch for bugfix-only, minor for features
```

Stage but don't commit yet — the version bump rides with the release
commit at the end.

---

## 3. Build the card bundle (if frontend changed)

```bash
npm run build
cp dist/eufy-vacuum-command-center.js \
   custom_components/eufy_vacuum/frontend/eufy-vacuum-command-center.js
```

Bundle is committed alongside the version bump.

---

## 4. Commit + tag + push

```bash
git add -A
git commit -m "release: vX.Y.Z"      # or use a conventional-commits-style msg
git tag -a vX.Y.Z -m "vX.Y.Z — short release summary

Bullets describing what changed since the previous tag. Reference any
fixed issues (Fixes #N) and any new capabilities."

git push origin master
git push origin vX.Y.Z
```

---

## 5. GitHub release

```bash
gh release create vX.Y.Z --title "vX.Y.Z — short title" --notes "$(cat <<'EOF'
Markdown-formatted release notes. Should mirror the tag annotation
content but with full markdown — links, code blocks, etc.

### Fixed
- Bullet about fix, with #issue references

### Added
- Bullet about new capability

### How to update
- Via HACS: ...
- Manual: ...
EOF
)"
```

---

## 6. Post-release verification

- ☐ <https://github.com/kingchddg901/eufy-vacuum-manager/releases/tag/vX.Y.Z>
  exists with the notes
- ☐ HACS will pick up the new tag on its next refresh (usually < 1 hr).
  No further action needed unless an existing user reports HACS still
  showing the old version after 24h.

---

## Bug-class checklist (informal — review yearly)

Cold-install bugs we've already hit. If something in this category gets
touched in a release, give it extra attention during step 1c–1f.

- [#1](https://github.com/kingchddg901/eufy-vacuum-manager/issues/1) — `OptionsFlow.__init__` setting `self.config_entry` (HA 2024.12+ regression)
- [#1](https://github.com/kingchddg901/eufy-vacuum-manager/issues/1) — unresolved `{context}` placeholder in translation strings
- [#2](https://github.com/kingchddg901/eufy-vacuum-manager/issues/2) — panel registration only iterated managed vacuums; fresh installs had zero
- `ICON_SELECTS` orphaned entities on the integration's device page (cleaned up in v0.9.3+)

Future bug classes to watch for:
- Static-path 404s for files that ship in the integration (textures, animal-svg, frontend bundle)
- Storage migrations that assume previous-schema shape
- Entity registry orphans when removing a platform
- `manifest.json` declared dependencies that aren't actually optional
