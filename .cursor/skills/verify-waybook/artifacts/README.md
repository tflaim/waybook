# Evidence location

Verification proof artifacts are written to `/tmp/waybook-verify-evidence/<run-id>/` by `control-waybook record` and `control-waybook snapshot`.

This directory is intentionally empty in git. Do not store disposable run transcripts here; keep them in the `/tmp` evidence root so `control-waybook cleanup` can delete the project instance without touching proofs.
