# Max assistant

Install Google Chrome to use Max's browser agent. On the first browser request,
Max launches a separate Chrome session with a fresh profile and uses its
initial tab. Later requests reuse that session. Closing Max ends the session
and discards its cookies and sign-ins.

The Apple agent loads every tool advertised by Apple MCP: Calendar, Reminders,
Notes, Contacts, Messages, Mail, and Maps. Native Music controls additionally
support playback, track skipping, library search, playlists, and Music volume.
Music search is limited to your library. macOS may request permission for each
app on first use; approve the relevant Automation, Calendar, Reminders, or
Contacts access in System Settings when prompted.

Examples: “Play music”, “Pause Apple Music”, “Play my Focus playlist”, “What is
on my calendar tomorrow?”, “Remind me to call the dentist tomorrow at 2 PM”,
and “Find directions to the nearest coffee shop in Apple Maps”.

## Computer control

The system agent can find local files/projects, open a project in VS Code or a
named app, move/rename individual regular files without overwriting, focus or
minimize windows, resize/tile them on the primary display, and open settings
panes. It can also change system volume and brightness (brightness requires the
`brightness` utility). File and project access is limited to Desktop, Documents,
and Downloads. Search skips hidden folders, dependencies, and build output.

For example, “Open VS Code and launch my SPEC2RTL project” searches for that
folder and opens it in VS Code. If several folders match, Max asks which one.
Opening a project does not automatically execute its code. Window controls and
desktop typing require macOS Accessibility and Automation permissions.

In **System Settings → Privacy & Security → Accessibility**, enable the app
you use to launch Max (for example, Terminal). On the first typing request,
allow that app to control **System Events** when macOS prompts, or enable it
under **Privacy & Security → Automation** if it is already listed. Max focuses
Claude's message composer automatically. In other apps, focus the desired
input before asking Max to type. Say “Open Claude Desktop and ask it why the
sky is blue” to submit a prompt, or “Type this in Claude” to leave a draft.

### Approved project commands

Commands use an argument list with no shell expansion or shell operators.
`pwd`, `git status --short`, and `git diff --stat` are available by default.
To approve another command, create `~/.config/max/approved_commands.json` yourself:

```json
[
  {
    "argv": ["python3", "-m", "unittest", "discover"],
    "cwd": "/Users/yourname/Desktop/SPEC2RTL"
  }
]
```

Both the complete argument list and resolved working directory must match.
Max cannot grant itself approval. Commands run in the foreground for at most
60 seconds; this tool is for bounded commands, not persistent development servers.
Command output is limited to 8,000 characters. No command approval file is needed
for opening a project in an editor.

### Automated checks

Run the isolated regression suite (without live app actions, network calls, or LLM calls):

```sh
python -B -m unittest discover -s tests -p 'test_*_tools.py'
python -B -m unittest discover -s tests -p test_browser_lifecycle.py
python -B -m unittest discover -s tests -p test_apple_agent.py
```

Other scripts in `tests` are manual integrations and can access the microphone,
open apps, or call live services; run them individually when needed.
