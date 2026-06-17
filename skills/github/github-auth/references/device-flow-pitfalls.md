# gh auth login device flow pitfalls

## The problem
`gh auth login` (with or without `--web`) prints a one-time code, opens a device
activation URL, and blocks waiting for the user to complete the flow in their
browser. Running it in foreground with any timeout makes the agent appear frozen —
the user sees no progress, and if the timeout expires the auth is lost.

The process MUST stay alive to receive the token callback from GitHub's servers
after the user authorizes. Killing it = starting over.

## Getting the code — Collar terminal restrictions

**WARNING: On Collar, both `--web` and `echo "" | gh auth login` get SIGINT (exit 130) in foreground mode.** The Collar terminal sandbox sends SIGINT to interactive-auth processes that wait for browser input. Do NOT use foreground mode.

**Bottom line: PAT (token) auth is the only reliable path in Collar.** After 1 failed device-flow attempt, switch to token auth unconditionally. Don't debug, don't retry, don't background — just ask for a PAT and use `--with-token`.

1. **Launch in background immediately** — don't try to grab the code in foreground:
   ```bash
   terminal(
     command="gh auth login --hostname github.com --git-protocol https",
     background=true, timeout=600
   )
   ```

2. **Poll for the code** after ~5s:
   ```bash
   process(action="log", session_id="<id>")
   # Will show: "First copy your one-time code: XXXX-XXXX"
   # Will show: "Open this URL: https://github.com/login/device"
   ```

3. **Open the URL** for the user:
   ```bash
   open "https://github.com/login/device"
   ```

4. **Wait for completion** — the background process stays alive and will receive the token:
   ```bash
   process(action="wait", session_id="<id>", timeout=120)
   ```

5. When done, run `gh auth setup-git` to wire git credentials.

### Fallback when background+log shows no output

Background processes may buffer stderr differently — the code might not appear in `process log`. If that happens:
- Tell the user to go to https://github.com/settings/tokens
- Generate classic token with `repo` scope
- `echo "<token>" | gh auth login --with-token`
- Then `gh auth setup-git`
- Done in one command, no blocking, no codes

## Alternative: skip the dance
If the user is impatient or the device flow fails after 2+ attempts:

- They go to https://github.com/settings/tokens
- Generate classic token with `repo` scope
- Paste it → `echo "<token>" | gh auth login --with-token`
- Then `gh auth setup-git`
- Done in one command, no blocking, no codes
