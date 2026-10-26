# Uploading your contribution

You are handling the GitHub upload yourself. No push, pull request, or team message has been sent.

The clean upload ZIP contains the contribution files in the team's existing repository structure.
It preserves the existing frontend README content and adds a link to the AI guide.
It excludes .env, .venv, local databases, and private run output.

## Recommended workflow

1. Start from a current clone of aklaosun/Conference-Intelligence-Planning-Platform.
2. Create an AI feature branch (or reuse your existing feature/ai-extraction branch).
3. Extract the clean upload ZIP into the repository root, preserving paths.
4. Review git status and the diff. Keep your .env and database untracked.
5. Run the tests using the README instructions.
6. Commit and push your branch, then open a pull request for teammates to review.

Do not drag the entire active Capstone project folder into GitHub's web uploader: ignored local files
still exist on disk, and a web uploader does not use Git's ignore rules.
If using the website, upload only the contents of the clean upload package to a feature branch.

The patch file is an alternative for an unchanged repository at base commit cedf839807229762120fe6dc0b97a27af2489bcd:
git apply --check AI-contribution.patch
git apply AI-contribution.patch

Merge newer teammate changes before applying if their code has changed.
The AI contribution does not replace the final review screen or change approval_service.py.
