# Installing the Forma User plugin

**Package:** `forma-user-v0.10.1-beta.plugin` (about 440 KB) — **BETA**: the
architecture for Assemble's cost-admin workflow is in place; contract steps 2 and 3
are still being built.

The everyday plugin, for Assemble's cost management in Autodesk Forma - budgets,
contingency, contracts, variations, invoices and progress claims.

It carries its skills in two groups, so most of what you will do with it is ask in
plain English rather than name a tool. `docs/skill-tree.svg` in the package draws
the whole tree.

**Cost admin** — moving cost records through Assemble's workflow

| | |
|---|---|
| **contract-bot** | A consultant contract from vendor selection to execution: the CRC Recommendation and the draft contract today; agreed terms, approval and the agreement as they are built. Hands over to its three step skills |
| **var-bot** | A variation, at any stage: flagged, priced, or recommended for approval. Produces Assemble's Variation Approval document and raises the records in Forma. Hands over to its three stage skills |
| **desk-bot** | Your own **Cost & Spend Desk**: one page of every contract, variation and invoice that has stopped moving, who is holding it, and the budget line it draws on. See section 9 |
| **scout-bot** | Reads Aconex (and your email, once connected) for things that move a contract or variation on, and suggests the next move on your desk's Next steps tab. See section 9 |

**Forma information** — finding things out

| | |
|---|---|
| **forma-user** | Questions about project money - what is committed, what is left, what a consultant has billed |

There is a second, restricted plugin (`forma-admin`) for calling the Autodesk
API directly. You do not need it for everyday work and it has its own guide. If
you install both, **you sign in only once** - they share the same stored sign-in.

Written for **Windows**, which is what most of us use. macOS differences are at
the end. Fifteen minutes, once.

Read section 1 before anything else. It is the one thing no amount of correct
installation can fix.

---

## Already have it installed? You are upgrading, not installing

Skip most of this. **Sections 2 and 3 do not apply to you** - Python is already
there, and your sign-in lives in `C:\Users\<you>\.forma-mcp\`, outside the plugin
folder, so replacing the plugin leaves it untouched.

1. **Remove the old version first, then install the new one** - both through the
   app's plugin manager. Prefer that to unzipping the new files over the old: an
   over-the-top copy leaves behind every file the new version dropped, and a
   stale leftover is a confusing thing to debug later.

2. **Run `python login.py setup` again.** The new copy ships with a generic
   interpreter name; this points it back at your actual Python.

3. **Start a NEW CONVERSATION.** This matters *more* on an upgrade than on a
   fresh install, and it is the step people skip. On a new machine nothing is
   running, so anything works. On an upgrade the **old server is already running
   with the old code loaded** and keeps answering until the conversation ends -
   so you can install a new version and see no change at all. Reopening the app
   resumes the same conversation and is not enough. `/mcp` -> Reconnect does the
   job too.

4. **Copy the router again** - section 8. It is one small file and a newer
   package may carry a newer one.

5. **Check it took.** Ask Claude to run the diagnostics tool and look for
   `plugin_version`. If that field is missing entirely you are on a build from
   before it existed, and the cause is almost always step 3.

6. **Delete the older `.plugin` files** from your Downloads once it works.
   Installing a stale one later is an easy mistake to make and a slow one to
   notice.

---

## 1. Before you start: is the app provisioned?

**Nothing below will work until this is done, and the symptom is silence.**

Autodesk requires this plugin's app to be registered against Assemble's Forma hub
by an **Account Admin**, under **Account Admin -> Custom Integrations**, by
client ID.

Until that happens you can sign in perfectly successfully and then see **no
projects at all**. Not an error, not a permission warning - an empty list, which
looks exactly like "you have no projects".

> **Ask an Autodesk Account Admin to confirm this plugin's client ID is
> provisioned for the hub before you go any further.**

You also need to be a member of at least one Forma project yourself. An Autodesk
login on its own is not enough.

**You must also be using the Claude Code desktop app** (or the `claude`
command-line tool). This plugin runs a small Python program on your own computer,
so it cannot work in a web browser at claude.ai. If you are reading this in a
browser tab, stop here and open the desktop app.

---

## 2. Install Python

Python 3.10 or later. **Nothing else to install - no `pip`, no packages.** Every
import in this plugin is Python standard library, so if you ever see a
`ModuleNotFoundError` naming an outside package, your Python install is broken
rather than incomplete.

This plugin launches **`python`** (not `python3`), which is the name the ordinary
Windows installer provides - so there is no renaming trick to do here.

*Route A - Microsoft Store (recommended at Assemble):*

```
winget install --id 9NCVDN91XZQP --source msstore
```

*Route B - python.org, if the Store is unavailable to you:*

```
winget install --id Python.Python.3.12
```

**Why the Store build is recommended here, against the usual advice.** Assemble
runs **ThreatLocker**, which allows or blocks applications by policy. A Python
downloaded fresh from python.org is a new, unrecognised executable and has been
blocked on at least one machine; the Store build arrives through a channel
ThreatLocker already trusts and has not been.

If Route B is blocked you will see Python install successfully and then fail to
run - the failure looks like the plugin being broken rather than like a policy
block. Use Route A, or ask IT to allow the interpreter.

The often-quoted objection to the Store build - that it cannot read inside
`AppData\Roaming` - **does not apply here**, verified on Windows 11 on
16 Sep 2026: plugins install under `.claude\plugins`, which the Store build reads
without trouble, and no staged copies were found elsewhere.

**If you have no Python at all**, typing `python` on Windows opens the Microsoft
Store rather than saying "not found". That is a placeholder, not Python. After
installing properly, turn the placeholder off: **Settings -> Apps -> Advanced app
settings -> App execution aliases -> toggle off `python.exe`**.

Confirm it worked. This must print a version, not an error and not a Store page:

```
python --version
```

**macOS** already has `python3` - use that name instead throughout.

---

## 3. Install the plugin

**Use the Claude Code desktop app's plugin installer** and upload
`forma-user-v0.10.1-beta.plugin`. This is the normal route and it is safe: the app installs to
`C:\Users\<you>\.claude\plugins\marketplaces\local-desktop-app-uploads\`, which
every build of Python can read - confirmed on Windows 11 with Store Python.

**Reinstalling? Section 4 is not optional for you either.** A fresh package
carries a generic interpreter name and overwrites whatever section 4 wrote last
time, so a plugin that worked yesterday stops connecting today.

**About `AppData\Roaming`.** You may have heard a warning about it. It is real -
the Store build of Python genuinely cannot see inside that folder - but it does
**not** apply to the app's installer, because plugins do not live there. The only
ways to hit it are to unzip the plugin there by hand, or to be on Store Python
when the app happens to run a staged copy it keeps under
`AppData\Roaming\Claude\local-agent-mode-sessions\...`. If you ever get a
nonsensical "file not found" on a Store-Python machine, that is the likely cause,
and Route A avoids it entirely.

---

## 4. Point it at your Python - REQUIRED on Windows, and again after every reinstall

In **Command Prompt**:

```
cd %USERPROFILE%\.claude\plugins\marketplaces\local-desktop-app-uploads\forma-user
```
```
python login.py setup
```

This writes the exact location of your Python into the plugin's configuration, so
it no longer depends on PATH at all, and then runs its own checks.

> **Why this step exists, and why it is not optional.** Typing `python --version`
> in Command Prompt proves nothing about what the Claude app will find: an app
> launched from the Start menu does not inherit your Command Prompt's settings.
> A tester on 16 Sep 2026 had a working `python --version` and still got
> `Connection closed`, because the app could not resolve `python` at all. This
> step fixed it.
>
> **It must be re-run after every reinstall and upgrade.** The packaged plugin
> ships a generic `"python"`, so installing over a working setup reverts it and
> the plugin stops connecting. That looks exactly like the upgrade having broken
> something.

In **PowerShell**, join two commands with `;` - **not** `&&`, which PowerShell
5.1 rejects with a parser error:

```
cd %USERPROFILE%\.claude\plugins\marketplaces\local-desktop-app-uploads\forma-user ; python login.py setup
```

---

## 5. Sign in, once

```
python login.py
```

This is the only step that needs a browser. **Skip it if you already signed in
for the other Forma plugin** - both share one sign-in.

1. **A browser window opens.** If it does not, the command prints a link - paste
   that in yourself.

2. **Sign in with your Assemble Autodesk account** - the same one you use for
   Forma. If a different Autodesk account is already signed in in that browser,
   sign out first or use a private window. This matters more than it looks:
   signing in as the wrong person works perfectly, against the wrong person's
   access.

3. **Autodesk asks you to allow "Assemble Claude Forma MCP"** to access your
   data. Click **Allow**. You will only see this once.

4. The page says **"Signed in to Forma"**. Close the tab.

5. Command Prompt shows **who you signed in as**:

   ```
   Signed in as:  Jane Smith   <jane.smith@assemble.com.au>

   ^ CHECK THIS IS YOU, and that it is your Assemble account.
   ```

   Wrong account? `python login.py logout`, then sign in again in a private
   browser window.

**What you are approving.** Read and write access to Autodesk data, plus
permission to refresh itself for about two weeks without asking again.
Autodesk's permissions are account-wide - there is no way to grant "write, but
only project X". What actually limits it is **your own Forma project
membership**, which this cannot change. It can only ever do what you could
already do in the Forma web interface.

Check any time with `python login.py status`.

---

## 6. Reconnect the server - do not just restart the app

If you installed Python *after* first trying the plugin, its server already
failed once, and **a failed server is never retried inside a conversation.**

**Do this first - one click, no terminal:**

> Type `/mcp`, find the **forma-user** row, choose **Reconnect**.

**Closing and reopening the app is usually not enough.** The desktop app resumes
your existing conversation, and the dead server comes back with it. If you cannot
use `/mcp`, start a **brand-new conversation** instead.

---

## 7. Check it works

Ask Claude:

> Which Forma projects can I see?

You should get a list with job numbers. **Do not expect a particular number** -
what you see depends entirely on your own Forma access, and it varies a lot
between people. Any list at all means it is working.

Then try a real question:

- *"How much contingency is left on Clayton?"*
- *"What was Webber Design's last invoice?"*
- *"How many invoices are sitting with me for approval?"*

Replace the project and consultant names with your own - those are examples, not
a test anyone expects to pass on every project.

---

## 8. Turn on the bots - one file to copy

The plugin ships its front doors — **contract-bot** (consultant contracts),
**var-bot** (variations), **desk-bot** (the Cost & Spend Desk), **scout-bot** (the
scout) and **forma-user** (reading project money) — and behind contract-bot and
var-bot, three step skills each, which the front doors hand over to themselves.

You can always invoke one by name - `forma-user:desk-bot`. But for them to fire
from an ordinary sentence ("refresh the desk", "do the approval for CV037",
"run the scout"), copy the small router skill that ships beside the plugin, in the
package's `router` folder, to your own skills folder:

In **Command Prompt**:

```
mkdir "%USERPROFILE%\.claude\skills\forma-bots"
copy "<where you unzipped>\router\forma-bots\SKILL.md" "%USERPROFILE%\.claude\skills\forma-bots\"
```

It holds no process knowledge of its own - just which bot to use for what - so
it is safe to overwrite with a newer one whenever you upgrade.

Then start a new conversation. Ask *"what forma bots do I have?"* to check.

---

## 9. Your own Cost & Spend Desk

Ask, in a new conversation:

> Build me a Cost & Spend Desk

It will ask **which projects** - it can see every project your Autodesk account
can, which is usually far more than you work on, so name the two or three you
want. Then it reads Forma, builds one page and gives you a private link.

The page has three tabs. **Cost** is contracts and variations; **Spend** is
invoices; **Next steps**, visible only to you, is scout-bot's suggestions. Each record shows its approval chain, who is holding it, how many days
past its review date it has sat, the budget line it draws on, and a link straight
to each of its attachments. It also offers to refresh itself on a schedule -
weekday mornings by default.

**It only ever contains what your own Autodesk account can see.** The filtering
is Forma's, not the page's.

**Decisions on it are queued, not sent.** The page has no route to Autodesk, so
approving there cannot commit anything. Queued decisions are carried out
afterwards in Forma, or by Claude with this plugin, one record at a time.

**If you share your desk, understand what you are sharing.** The figures are
built into the page, so everyone with the link sees **every record on it** -
contract sums, vendors, budget positions - whatever the page chooses to
highlight. Share it inside Assemble, never as a public link, and only when you
mean to. A desk you want per-person is a desk each person builds for themselves.

**The Next steps tab is yours alone.** scout-bot reads Aconex (and your email,
once connected) and writes suggested moves there — "the lawyers have closed out
their comments, so this contract can be submitted". You mark each one **Proceed**
or **Hold**, with a comment. The tab is hidden from anyone you share the desk with,
and its data is readable only by you. Ask *"run the scout"* to fill it, and
*"process my next steps"* to carry out what you marked Proceed — every Forma write
is still shown to you and confirmed in chat first.

---

## Troubleshooting

### Claude finds the skill but says it has no Forma tools

The commonest failure, and it looks alarming. If Claude can see the Forma skill
but reports that tools like `forma_projects` are unavailable, **the plugin is
installed correctly** - its local server just did not start.

It is not a permissions problem, it does not need an org owner to enable it, and
it will not appear under Settings -> Connectors. **Ignore any advice pointing
there** - Claude guesses badly at this particular failure and will often suggest
exactly that.

In order:

1. **Are you in the Claude Code desktop app?** Not a browser.
2. **Does `python --version` print a version?** If it opens the Microsoft Store,
   that is the placeholder, not Python - see section 2.
3. **Did you run `python login.py setup`?** See section 4.
4. **Did you reconnect the server?** `/mcp` -> Reconnect. A server that failed
   once is never retried inside a conversation, and reopening the app resumes
   that same conversation - so the failure persists.

### "Skipping connection (recent failure cached)"

The client has given up on the server for the rest of this conversation, and a
reconnect can be refused outright. That state lives in memory, so there is
nothing to delete on disk - **start a new conversation.**

### Do NOT re-run login.py to fix a connection failure

A common wrong turn, and worth stating plainly.

This server starts and serves all of its tools **with no sign-in at all** -
authentication is checked per call, not at startup. So an expired sign-in
produces *tool errors*, never "failed to connect" or "recent failure cached".

Ask Claude for the diagnostics: if `needs_sign_in` is **false**, your sign-in is
fine and the cause is elsewhere, whatever else it says.

Note that `access_token_live: false` is **normal and harmless** - access tokens
last an hour and the next call renews silently from a refresh token that lasts
fifteen days. Only `needs_sign_in: true` requires you to do anything.

### It says it can see Forma, but no projects come back

Almost always section 1 - the app is not provisioned for the hub. Sign-in
working is not evidence against this; sign-in works fine either way.

### Sign-in problems

| What you see | What it means |
|---|---|
| Browser does not open | Paste the printed link in manually |
| "Timed out after 5 minutes" | Sign-in was not finished. Run `python login.py` again |
| "Could not start the sign-in listener on port 8080" | Something else is using that port. The message tells you how to find it. The port cannot be changed - Autodesk has it registered |
| A Windows firewall prompt | Allow it. The listener only accepts connections from your own machine and closes the moment sign-in finishes |
| Signed in as the wrong person | `python login.py logout`, then sign in again in a private browser window |

### The token '&&' is not a valid statement separator

You are in Windows PowerShell, which does not accept `&&`. Use `;` instead.

### Nothing above helped

Ask Claude to run the **diagnostics** tool. It writes a file you can send on. It
contains **no passwords or tokens** - that is checked automatically before it is
written.

If Claude cannot run any tools at all, run this in Command Prompt instead:

```
python login.py diagnose
```

---

## macOS

Identical, with two differences: use `python3` instead of `python`, and the
folder is:

```
cd ~/.claude/plugins/marketplaces/local-desktop-app-uploads/forma-user ; python3 login.py setup
```

Install Python from <https://www.python.org/downloads/> or Homebrew. Do not rely
on the `python3` that macOS ships - on a machine without Xcode command line tools
it can pop up an installer dialog instead of running.

---

## What it can and cannot do

**Can**: answer questions about budgets, contingency, contracts, variations,
invoices and progress claims; draft contracts and variations, amend drafts, link
budgets, add fee stages and attach documents; walk a variation through its
internal pricing steps; pull cost data across projects; produce Assemble's
Variation Approval and CRC Recommendation documents; build and refresh your Cost &
Spend Desk; and suggest next moves from Aconex.

**Cannot**: move a record except where its **workflow rules** allow — the steps
Assemble's mapped process gives to a bot, each measured on the sandbox first.
Today that is only a variation's internal pricing walk, which notifies nobody.
Sending a contract or Approved Variation into approval, approving, executing and
closing are all refused here - a person does those in Forma, where the approval
workflow can see them. This is enforced by the plugin, not merely left undone:
Forma itself will accept a status write on a contract that is sitting in an
approval workflow, skip the step rather than answer it, and record nothing.

It also cannot write without you confirming that specific call, or touch the
NetSuite integration. **Project confinement is off by default**, so a confirmed
write lands in whichever project it names — production included. Your confirmation
is the gate; read the project name before you give it.

Correspondence, drawings and RFIs live in Oracle Aconex, not here. This plugin
cannot touch Aconex.

---

## A note on Beta

Autodesk's Forma APIs are marked **Beta** and still changing. Something that
worked last month may behave differently today. If a figure looks wrong, say so
rather than assuming - the plugin keeps a record of the places Autodesk's own
documentation is incorrect, and that list is still growing.

Questions: Jarvis Mellor.
