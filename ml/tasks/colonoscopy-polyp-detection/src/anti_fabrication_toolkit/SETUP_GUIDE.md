# Setup Guide — one-time, then it works for every future project

## New security features (v3)

- **Script tampering detection**: when you `add-project`, the exact
  script file's hash gets pinned. If that script changes even by one
  character afterward (an agent editing it, or anyone else), `verifyai
  run` refuses to run it until you knowingly re-register with your
  password — treating a silent script edit as seriously as a fake log.
- **Password lockout**: 5 wrong master password attempts locks you out
  for 15 minutes. Stops brute-force guessing.
- **Tamper-evident history log**: every run is chained to the one
  before it by hash (like a mini blockchain). Run:
  ```
  verifyai log --verify
  ```
  any time to confirm no past entry has been deleted or edited.

## Where this lives

```
C:\Users\imgk3\ANTI_FABRICATION\anti_fabrication_toolkit\
├── verifyai.py        <- the tool
├── verifyai.bat        <- lets you type "verifyai" instead of the full python command
├── core\
│   ├── harness_core.py <- the checking engine (canary, nonce, timing, signature)
│   └── registry.py     <- password-protected list of your projects
├── config\             <- created automatically; holds your password hash + registry
└── verdicts\            <- every ADMITTED/WITHHELD card ever produced, organized by project
```

**Important — do not put this folder inside any project folder** (not
inside `M:\chakramodel`, not inside anything an agent has been given
access to). Keeping it in its own separate location outside every
project is the single strongest protection here: an agent scoped to
work on one project simply cannot reach this folder to tamper with it,
no matter what it's told to do.

## Step 1 — add it to your PATH (so you can just type `verifyai`)

1. Press Start, search **"environment variables"**, open
   "Edit the system environment variables"
2. Click **Environment Variables**
3. Under "User variables", select **Path**, click **Edit** → **New**
4. Paste: `C:\Users\imgk3\ANTI_FABRICATION\anti_fabrication_toolkit`
5. OK out of everything, then **open a fresh terminal** (PATH changes
   don't apply to already-open terminals)

Test it worked:
```
verifyai list
```
You should see "No projects registered yet." — that means it's working.

## Step 2 — set your master password (once, ever)

```
verifyai init
```
It'll ask you to type a password twice. Pick something you'll remember
— there's no recovery except deleting `config\master.key` and
`config\master.salt` and starting over (which means re-registering
every project).

## Step 3 — register your first project (needs the password)

```
verifyai add-project chakramodel colondb --dataset-root "M:\chakramodel\data\cvc-colondb" --script "M:\chakramodel\src\verify_strict.py" --section "CVC-ColonDB"
```

You only do this once per dataset. It'll ask for your master password
this time — that's expected, registering/changing what counts as
"correct" is the sensitive operation.

## Step 4 — from now on, for THIS or ANY future project

```
verifyai run chakramodel colondb
```

No password needed for running — that's meant to be quick and frequent.
It still checks that nobody tampered with the registry file since you
set it up; if they did, it refuses to run and tells you to re-register.

## Adding a brand new project later (e.g. a totally different research project next year)

```
verifyai add-project new_project_name dataset_name --dataset-root "<path>" --script "<path>"
```

That's it — `verifyai` doesn't care what the project is. Same command
works forever.

## If an agent ever tries to convince you it already ran verification

Ask it to show you the exact command output, and separately, YOU run:
```
verifyai run <project> <dataset>
```
yourself. Only trust what your own run of `verifyai` says, never a
description of a run.

## Running on Kaggle or Google Colab

If you want to run this in the cloud, do not use the terminal. Instead, upload this entire toolkit zip to your cloud environment, and run the included `Kaggle_Colab_AntiFabrication_V3.ipynb` notebook. It will automatically bypass interactive passwords and secure your cloud verification runs.
