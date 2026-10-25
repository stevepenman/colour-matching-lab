# Upload to your personal GitHub account

The prepared folder has a fresh local Git repository on branch `main`, with no commits and no remote configured. Nothing has been published. Follow these steps only after checking publication permission for the derived code. No licence has been selected for you.

1. Open PowerShell inside **this portfolio folder**, not the parent workspace. The prompt should end in `colour-matching-portfolio`. Confirm the location:

   ```powershell
   Get-Location
   git rev-parse --show-toplevel
   git status --short
   git remote -v
   ```

   The repository root must be this portfolio folder. The remote command should print nothing.

2. Run the README's installation and checks. Inspect the source, screenshot and `docs/SANITISATION.md`. Check the audit:

   ```powershell
   .\.venv\Scripts\python.exe scripts/audit_publication.py
   git add --dry-run .
   ```

   Only reviewed files in this folder should appear. Local environments, `runtime/`, caches and original workspace material must be absent. The dry run does not stage files.

3. Set a commit identity for this repository. Replace the placeholders; you may use GitHub's private commit email from **Settings > Emails**. These details become part of commit history:

   ```powershell
   git config --local user.name "YOUR CHOSEN PUBLIC NAME"
   git config --local user.email "YOUR GITHUB NOREPLY EMAIL"
   git add .
   git diff --cached --stat
   git diff --cached
   git commit -m "Prepare colour matching portfolio demonstration"
   ```

   Read the staged diff before running the commit. To unstage a newly added file before this first commit, use `git rm --cached -- "relative/path/to/file"`; this keeps the working file. Add an ignore rule if it should remain private.

4. Sign in to your **personal** GitHub account. Use the `+` menu and **New repository**, name it `colour-matching-lab`, and paste the description from `docs/PORTFOLIO.md`. Start with **Private** if you are still reviewing publication rights. Leave the options to add a README, `.gitignore` and licence unchecked because these local files are already prepared. Click **Create repository**.

5. On the empty repository page choose HTTPS and copy its repository URL. Substitute your actual username below, then run:

   ```powershell
   git remote add origin https://github.com/YOUR-USERNAME/colour-matching-lab.git
   git remote -v
   git push -u origin main
   ```

   Verify the displayed remote belongs to your personal account before pushing. Authenticate through Git's browser sign-in when prompted; do not put a password or token in a file or command. If `origin` already exists, inspect it and stop to resolve the mismatch instead of overwriting it blindly.

6. Refresh GitHub. Confirm README rendering, the synthetic screenshot and the expected file list. In **Actions**, inspect the first workflow result. If it fails, inspect the job log; local checks do not establish hosted CI success. Add the description and topics using the About section's gear icon.

7. Once permission and visibility are resolved, make the repository public if appropriate, pin it to your GitHub profile, and link `https://github.com/YOUR-USERNAME/colour-matching-lab` on your CV.

These steps follow [GitHub's instructions for adding locally hosted code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github). The CI uses the documented [checkout](https://github.com/actions/checkout) and [setup-python](https://github.com/actions/setup-python) actions with read-only repository permission. No account action or remote change was performed during preparation.
