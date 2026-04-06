# Claude Code Status Line Fix

## Symptoms

- No status bar visible at the bottom of Claude Code
- Model name not displayed
- Context bar not shown
- Status line "enabled" but not appearing

## Root Causes & Fixes

### 1. The statusLine script is not executable

The script Claude Code runs for the status line must have execute permissions.

```bash
chmod +x ~/.claude/statusline-command.sh
# or for the GSD statusline:
chmod +x ~/.claude/hooks/gsd-statusline.js
```

### 2. The statusLine config is missing from settings.json

Claude Code reads the `statusLine` config from `~/.claude/settings.json`. Putting it only in `settings.local.json` does **not** work — it is silently ignored.

Add this to `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/home/YOUR_USER/.claude/hooks/gsd-statusline.js"
  }
}
```

**Important:** Use the full absolute path. `~` is not expanded in this field.

### 3. Tilde (~) paths are not expanded

Even if the config is in the right file, `~/.claude/...` will not work as the command path. Always use the full path:

```json
"command": "/home/bamn/.claude/hooks/gsd-statusline.js"
```

## Correct Final Config (settings.json)

```json
{
  "statusLine": {
    "type": "command",
    "command": "/home/bamn/.claude/hooks/gsd-statusline.js"
  }
}
```

## Testing the Script

You can verify the script works before restarting:

```bash
echo '{"model":{"display_name":"Claude Sonnet 4.6"},"workspace":{"current_dir":"/your/dir"},"context_window":{"remaining_percentage":80}}' \
  | node ~/.claude/hooks/gsd-statusline.js
```

Should output something like:
```
Claude Sonnet 4.6 │ yourdir ██░░░░░░░░ 24%
```

## Summary

| What went wrong | Fix |
|---|---|
| Script not executable | `chmod +x` the script |
| Config in `settings.local.json` | Move to `settings.json` |
| Path uses `~` | Use full absolute path `/home/user/...` |

Restart Claude Code after making changes.
