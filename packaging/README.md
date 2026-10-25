# Running agentwit as a service

agentwit's daemon is a **single process** (one worker, one thread at idle,
no child processes). On a 4–8 GB machine it sits around **60–70 MB RSS** and
barely moves under load, so it is safe to leave resident alongside other apps.

First-time setup (both platforms):

```bash
agentwit init                 # creates ~/.agentwit/{config.yaml,secrets.env}
$EDITOR ~/.agentwit/secrets.env   # add webhook URLs / SMTP creds (chmod 600)
agentwit config set proxy.target http://localhost:3000
agentwit config validate
```

Secrets live only in `~/.agentwit/secrets.env` and are referenced from
`config.yaml` as `${env:NAME}` — nothing secret is ever committed or shipped.

---

## Linux (systemd user service)

```bash
mkdir -p ~/.config/systemd/user
cp packaging/systemd/agentwit.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agentwit

# apply config changes WITHOUT dropping the socket:
systemctl --user reload agentwit      # sends SIGHUP

systemctl --user status agentwit
journalctl --user -u agentwit -f      # live logs
```

The unit caps memory (`MemoryMax=192M`) and CPU (`CPUQuota=50%`) and runs
hardened (`NoNewPrivileges`, `ProtectSystem=strict`, loopback+outbound
sockets only). Keep `proxy.host` at `127.0.0.1` unless you truly need the
proxy reachable from other machines.

To keep the daemon running after you log out:
`loginctl enable-linger $USER`.

---

## macOS (LaunchAgent)

```bash
cp packaging/launchd/io.agentwit.daemon.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/io.agentwit.daemon.plist

# reload config without a restart:
launchctl kill -HUP gui/$(id -u)/io.agentwit.daemon

# stop / remove:
launchctl unload ~/Library/LaunchAgents/io.agentwit.daemon.plist
```

If `agentwit` is not at `/usr/local/bin/agentwit`, edit the first
`ProgramArguments` string to the path from `which agentwit`.

---

## Signals

| Signal  | Effect                                              |
| ------- | --------------------------------------------------- |
| SIGHUP  | Re-read `config.yaml`; on error the old config is kept |
| SIGTERM | Graceful stop (finish in-flight, remove pidfile)    |
| SIGINT  | Graceful stop (same as SIGTERM)                     |
