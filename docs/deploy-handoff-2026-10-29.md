# Deployment handoff — 29 October 2026

**Update, 30 October:** the latest `main` also includes notebook/textbook grouping.
Startup now applies additive migration **0005**, and the parent must approve science
**v5** instead of v4. Textbook topics start inactive; activate them individually only
when covered at school. See [source groups and activation](science-source-groups.md).
The private photo transfer and deployment procedure below still apply.

The `main` branch combines the local science classroom, English collection, Alan's music
materials, local household startup improvements and Foxy exercise-state fixes with the
English video lessons from upstream commit `d41d050`. No production deployment was run.

## For Danijel

1. Pull the latest `main` into a clean checkout before deploying; do not deploy an older local folder.
2. Transfer the science source photographs privately. The 38 prepared files are in
   `data/files/study/danijel/2026-10-28-erik-naravoslovje/` on the authoring PC. Copy that
   directory to `/opt/ucilnica/data/files/study/danijel/2026-10-28-erik-naravoslovje/`
   on the server using authenticated SSH/SFTP, preserving filenames and readable ownership
   for the existing application user. The deployment archive excludes `data/`.
   These textbook pages and worksheets must remain outside GitHub.
   See [science setup](erik-naravoslovje.md) for importing the originals on another PC.
3. Follow [the existing deployment procedure](../deploy/DEPLOYMENT.md):

   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1
   powershell -ExecutionPolicy Bypass -File deploy\smoke-test.ps1
   ```

   Startup applies additive migration `0004`, creating `lab_progress` without replacing
   existing tables. The deployment procedure backs up the database and private files.
4. In the parent content studio, approve the desired current versions for each child:
   Erik's science v4, English People and Days v6 (upstream video additions), and Alan's
   music topic/mock v1. Existing production approval rules still apply. Keep content IDs
   and the server's existing data directory; do not import the local development database.
5. Verify Erik's classroom shows **Angleščina**; open both lessons, their video lessons,
   and the People practice test. Closing English activities returns to Angleščina.
   Open science picture exercises to confirm the private images load. Check the mobile
   layout and require the standard production smoke test to report zero failures.

## Validation before handoff

- 76 backend tests pass using scratch databases, including tenancy and progress tests.
- 55 frontend tests pass, including English collection/video navigation and Foxy state.
- Content checker passes: 7 topics and 3 mocks.
- TypeScript and the Vite production build pass.
- Scratch-account browser check confirms the merged video opens from the collection and
  returns to Angleščina on exit.
- The existing classroom content IDs, practice scoring and saved progress storage are retained.
  The English collection itself does not edit educational content; upstream v6 video content
  is included unchanged.

Local source photographs, old export bundles, databases, credentials, dependency directories
and build output are excluded from Git. This handoff publishes source to GitHub only.
