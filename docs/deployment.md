# Deployment

Production runs on the college server (RHEL 9) as a rootful Podman container managed by systemd through a [Quadlet](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) unit. The files are in [`deploy/`](../deploy).

> Status: written for v1.0 before it was ever deployed. Check the steps against the server on the first rollout and fix this page.

## One-time setup

```sh
# Marker that allows the production bot token on this host (see "Production guard")
mkdir -p /etc/ghislieri && touch /etc/ghislieri/production

# Settings without secrets
cp deploy/ghislieri.env.example /etc/ghislieri/ghislieri.env   # then edit it

# Secrets
printf '%s' "<production bot token>" | podman secret create ghislieri-bot-token -
printf '%s' "<gmail app password>"  | podman secret create ghislieri-smtp-password -

# Unit
cp deploy/ghislieri.container /etc/containers/systemd/
systemctl daemon-reload
```

## Release

```sh
git pull
podman build -f deploy/Containerfile -t ghislieri:latest .
systemctl restart ghislieri
journalctl -u ghislieri -f        # or: podman logs -f systemd-ghislieri
```

The unit restarts the bot after a crash or after **Admin → Sistema → Riavvia** (exit code 75), not after a clean stop (exit code 0: `systemctl stop`, or **Arresta** in the bot). After **Arresta** start it again with `systemctl start ghislieri`.

Keep the previous image for rollback: `podman tag ghislieri:latest ghislieri:previous` before building.

## Data

Everything lives in the named volume `ghislieri-data`, mounted at `/data`:

- `ghislieri.sqlite3`: the database (users, meals, notifications, submissions, calendar);
- `calendar.ics`: the calendar export, rewritten on every change.

Back up with the database's own backup command, which is safe while the bot runs:

```sh
podman exec systemd-ghislieri python -c \
  "import sqlite3; sqlite3.connect('/data/ghislieri.sqlite3').backup(sqlite3.connect('/data/backup.sqlite3'))"
```

## Production guard

The bot refuses to start if:

- the token belongs to the production bot (`settings.PROD_BOT_ID`) but `GS_ENV` is not `prod` or `/etc/ghislieri/production` is missing, or
- `GS_ENV=prod` but the token is not the production bot's.

So the production token cannot run on a development machine by mistake, and the test token cannot reach production.

## Printing

The container runs `lp` against the host's CUPS through the mounted socket `/run/cups/cups.sock`. SELinux may block the socket; if printing fails with a permission error, check `ausearch -m avc` on the host.

## Migrating from v0.5

1. Stop the old service: `systemctl stop ghislieri_services` (and disable it).
2. Copy the old data directory (`/var/opt/ghislieri_services`) somewhere readable.
3. Run the import into the new volume (see [migration.md](migration.md)).
4. Start the new unit and check the logs and the bot.
5. Keep the old data directory until the new version has run for a while.
