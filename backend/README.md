# Backend deployment

This folder contains the small serverless state service that unlocks stages 1 and 2 by time and lets you manually unlock any stage from a private admin page.

## What it does

- Stage 1 unlocks at `2026-06-08T18:00:00Z` by default.
- Stage 2 unlocks at `2026-06-09T07:00:00Z` by default.
- Stage 3 and 4 still unlock when the previous stage is solved.
- Manual override is available through the admin endpoint.

## Deployment

The template is a SAM/CloudFormation stack. The only required parameters are:

- `AdminToken` for the manual override page.
- `Stage1UnlockAt` if you need a different UTC unlock moment.
- `Stage2UnlockAt` if you need a different UTC unlock moment.

Typical deploy flow:

```bash
cd backend
sam build
sam deploy --guided
```

When the deployment completes, copy the `FunctionUrl` output into `app-config.js` at the repo root:

```js
window.FYME_CONFIG = {
  apiBaseUrl: "https://your-lambda-function-url.lambda-url.region.on.aws"
};
```

Then push the config change so the live site can talk to the backend.
