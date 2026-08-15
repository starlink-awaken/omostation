# Submodule Bump Bot Pilot Notes (omlxc)

This document provides instructions for operators to configure the `OMOSTATION_BOT_TOKEN` secret required for the automated submodule bump PR workflow in `projects/omlxc`.

## Background
We are piloting a "submodule release -> auto PR -> main repo" mechanism for `omlxc`. When a `v*` tag is pushed to `omlxc`, a GitHub Actions workflow will automatically create a PR in the main `omostation` repository to update the submodule pointer and `project-registry.yaml`.

## Configuration Steps

1. **Create a Fine-grained Personal Access Token (PAT):**
   - Log in to GitHub as a bot account or an admin.
   - Go to **Settings** > **Developer settings** > **Personal access tokens** > **Fine-grained tokens**.
   - Click **Generate new token**.
   - **Repository access**: Select `Only select repositories` and choose `starlink-awaken/omostation`.
   - **Permissions**:
     - **Contents**: Read and write (required to push branches).
     - **Pull requests**: Read and write (required to create PRs).
   - Generate the token and copy the value.

2. **Add the Secret to the Submodule (`omlxc`):**
   - Navigate to the `omlxc` repository on GitHub: `https://github.com/starlink-awaken/omostation-omlxc`.
   - Go to **Settings** > **Secrets and variables** > **Actions**.
   - Click **New repository secret**.
   - **Name**: `OMOSTATION_BOT_TOKEN`
   - **Secret**: Paste the generated PAT.
   - Click **Add secret**.

The automated workflow is now fully configured and will trigger on the next `v*` tag push.
