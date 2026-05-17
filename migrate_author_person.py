#!/usr/bin/env python3
"""
Migrate `author` JSON-LD from Organization → Person (Robert Kiesling).

Idempotent: if author is already a Person matching the canonical block, leaves it alone.
Conservative: does NOT add knowsAbout, specialties, expertise claims, or past-results
language, and does NOT include the bar number (Zero preference 2026-05-17 — keep
personal-identifier broadcast off the structured-data surface; the firm bio page handles
disclosure).

Per Codex adversarial review 2026-05-17 (TX TDRPC §7.02/§7.03):
  - No "specialist" / "expert" framing
  - No past-results / case-wins references
  - No practice-area sprawl (no knowsAbout array)
  - Required disclosures stay on existing bio/disclaimer pages, not in schema

Usage:
  python3 migrate_author_person.py [--apply] [--single <slug>]
  Default is DRY-RUN. --apply writes files in place after backup.
"""
import sys, os, json, shutil, datetime, argparse
from bs4 import BeautifulSoup

PUBLIC_DIR = "/home/memory451/rrk-blog-railway-deploy/public"

# TX-bar-compliant Person block. No specialty/expert/results claims.
# worksFor uses @type: Organization (per Codex review 2026-05-17: worksFor is
# defined for Organization; LegalService is technically valid but unnecessary).
# Firm name "Law Offices of RRK, LLC" is the canonical brand — matches existing
# publisher field on all 30 articles + email signature + rrk_legal_standards.md.
# Bar number REMOVED per Zero 2026-05-17 — Texas bar number is publicly
# searchable on texasbar.org but Zero does not want it broadcast in structured
# data on every article. Person + name + worksFor + bio url is sufficient for
# named-author attribution; bar number adds personal exposure for no real gain.
PERSON_AUTHOR = {
    "@type": "Person",
    "name": "Robert Kiesling",
    "jobTitle": "Attorney",
    "worksFor": {
        "@type": "Organization",
        "name": "Law Offices of RRK, LLC",
        "url": "https://rrklawoffice.com/"
    },
    "url": "https://rrklawoffice.com/our-lead-attorney"
}

HTML_META_AUTHOR = "Robert Kiesling"


def migrate_file(path, apply=False):
    """Returns dict with action and notes. If apply=False, writes nothing."""
    with open(path, 'r', encoding='utf-8') as f:
        original = f.read()
    soup = BeautifulSoup(original, 'html.parser')

    blocks = soup.find_all('script', type='application/ld+json')
    changes = []
    blogposting_found = False

    for block in blocks:
        try:
            data = json.loads(block.string)
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get('@type') != 'BlogPosting':
            continue
        blogposting_found = True

        cur = data.get('author', {})
        # Idempotency: skip only if author block EXACTLY matches the canonical Person.
        # If it's already Person but with stale subfields (e.g. old worksFor type),
        # overwrite — that's the whole point of running this again.
        if cur == PERSON_AUTHOR:
            continue  # already canonical, no change needed

        # Replace author
        data['author'] = PERSON_AUTHOR
        prior_type = cur.get('@type') if isinstance(cur, dict) else 'unknown'
        changes.append(f"author: {prior_type} → Person (Kiesling)")

        # Rewrite the JSON-LD block. Preserve original indentation style (2-space).
        block.string = json.dumps(data, indent=2)

    # Update <meta name="author"> if present and not already Kiesling
    meta_author = soup.find('meta', attrs={'name': 'author'})
    if meta_author and meta_author.get('content') != HTML_META_AUTHOR:
        old = meta_author.get('content', '')
        meta_author['content'] = HTML_META_AUTHOR
        changes.append(f'<meta name="author">: "{old}" → "{HTML_META_AUTHOR}"')

    if not blogposting_found:
        return {"path": path, "action": "NO_BLOGPOSTING", "changes": []}

    if not changes:
        return {"path": path, "action": "NO_CHANGE", "changes": []}

    if apply:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(str(soup))

    return {"path": path, "action": "MODIFIED" if apply else "WOULD_MODIFY", "changes": changes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='Actually write files (default: dry-run)')
    ap.add_argument('--single', help='Operate on a single slug (without .html)')
    args = ap.parse_args()

    if args.single:
        files = [os.path.join(PUBLIC_DIR, f"{args.single}.html")]
    else:
        files = sorted(
            os.path.join(PUBLIC_DIR, f)
            for f in os.listdir(PUBLIC_DIR)
            if f.endswith('.html') and f != 'index.html'
        )

    if args.apply and not args.single:
        # Bulk backup
        stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = f"/tmp/blog_author_backup_{stamp}"
        os.makedirs(backup_dir, exist_ok=True)
        for f in files:
            shutil.copy2(f, backup_dir)
        print(f"Backup written: {backup_dir}\n")

    results = []
    for f in files:
        try:
            r = migrate_file(f, apply=args.apply)
        except Exception as e:
            r = {"path": f, "action": "ERROR", "changes": [str(e)]}
        results.append(r)

    # Print summary
    actions = {}
    for r in results:
        actions.setdefault(r['action'], 0)
        actions[r['action']] += 1
    print("Summary:")
    for a, n in sorted(actions.items()):
        print(f"  {a}: {n}")
    print()
    print("Per-file detail:")
    for r in results:
        slug = os.path.basename(r['path']).replace('.html', '')
        print(f"  [{r['action']:14}] {slug}")
        for c in r['changes']:
            print(f"      - {c}")


if __name__ == '__main__':
    main()
