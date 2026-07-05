#!/bin/bash
# SessionStart-Hook: setzt die Commit-Identitaet auf den verifizierten
# GitHub-Account von fl0w, damit KI-/Automatik-Commits aus Claude-Code-
# Web-Sessions dem eigenen Contribution-Graph zugerechnet werden.
#
# Hintergrund: In der Web-Umgebung ist die git-Identitaet standardmaessig
# "Claude <noreply@anthropic.com>". Diese Adresse ist keinem GitHub-Konto
# zuordenbar -> Commits zaehlen nicht. Wir ueberschreiben sie repo-lokal
# mit der bereits verifizierten GitHub-noreply-Adresse.
set -euo pipefail

# Nur in der Remote-/Web-Umgebung noetig; lokal gilt die eigene globale Config.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

git config user.name "fl0w"
git config user.email "122696700+flow-84@users.noreply.github.com"

echo "Commit-Identitaet gesetzt: fl0w <122696700+flow-84@users.noreply.github.com>"
