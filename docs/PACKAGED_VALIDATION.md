# Packaged demo validation — October 31, 2026

Result: ready for a Windows x64 local prototype walkthrough on the tested machine.

The exact portable executable was launched from a fresh isolated profile, exercised over HTTP against its bundled backend, closed through the application window, and relaunched. The project launcher and extracted-folder build were also started from a separate fresh profile.

The source regression suite previously passed 186 tests. The release completed the following packaged-runtime check groups:

- PASS: Packaged HTTP login and CSRF
- PASS: Fresh packaged seed: 35 real conferences and 35 editions
- PASS: Packaged React JavaScript and CSS are served
- PASS: Catalog search/year filter, manual entry/edit pages and all main API screens
- PASS: Embedded real-source review workbench
- PASS: Plan/budget save, decimal amounts, unknowns, explicit zero and separate currencies
- PASS: Outcome/follow-up save and planning CSV contents
- PASS: Evaluation approval gate and weighted calculation
- PASS: Packaged review approval/rejection, original-payload preservation and no duplicate catalog record
- PASS: Packaged Viewer role cannot edit plans
- PASS: Private key save through packaged backend without returning the secret
- PASS: Live Gemini extraction through packaged Python/SSL/provider stack
- PASS: Clean window close terminates bundled backend
- PASS: Exact portable restart retains plans, amounts, outcomes, ratings and private key configuration
- PASS: Project Run-Desktop.ps1 launches packaged folder build with fresh clean real data
- PASS: Distribution ZIP CRC and seed isolation

The clean distribution has 35 conferences, 35 editions, 10 source-backed deadlines, six source-backed prices, and three previously captured real extraction candidates. It contains no QA plans, outcomes, evaluation settings, test accounts, private database, or Gemini key. The ZIP passed CRC verification; SHA256SUMS.txt identifies the release files.

Use the Windows ZIP for repeat demonstrations: extract all files and open the executable inside the CCSE Conference Workspace folder. No Python, Node.js or PostgreSQL installation is needed. The alternative portable EXE successfully passed first launch and restart, but unpacking took about a minute on this computer.

Live Gemini extraction succeeded using the existing private key in an isolated QA profile. The key was cleared from that disposable profile after testing and was never included in the release. Each recipient supplies their own key for live extraction. Normal catalog, planning, saved evidence review and reporting do not require a key.

These checks cover this Windows x64 environment. Recipients should perform a quick first launch on their own computers before presenting. The separate local demos do not synchronize. Sponsor criteria/weights, final acceptance and other project-plan gaps remain documented in REQUIREMENTS_STATUS.md. The optional installer executable was built earlier; this acceptance run validates the portable and extracted-folder distributions, not a system installation/uninstallation cycle.
