# CI/CD

## CI (`.github/workflows/ci.yml`)

Runs on every push (any branch) and every pull request into `master`:
lints with `ruff` and runs the full `pytest` suite on Python 3.10 and
3.11. No AWS credentials are needed - every test in this repo mocks or
injects its AWS/Bedrock dependencies (see README's "Project status"),
so CI works with zero secrets configured.

Nothing to set up. This is on and enforced from the first push of
these workflow files.

## CD (`.github/workflows/cd.yml`)

Runs on every push to `master` (i.e. after a PR merges) and can also
be run manually from the Actions tab.

- **`build` job** (always runs): re-runs the test suite, then zips
  `src/ingestion`, `src/processing`, `src/rag`, and `requirements.txt`
  into a deployment artifact and uploads it to the workflow run. This
  needs no AWS access and works today.
- **`deploy` job** (off by default): pushes that artifact to real AWS
  resources. It is skipped until you turn it on, because those
  resources don't exist yet - see README's "Not yet started" list
  (no Terraform/CDK, no deployed Lambda/ECS task, no DynamoDB table,
  no Bedrock access configured).

### Turning `deploy` on, once infra exists

1. Write the actual infrastructure (Terraform or CDK, per
   `infra/README.md`) and note the real resource names/ARNs it
   creates (ingestion Lambda or ECS task, processing Lambda,
   DynamoDB table).
2. Under repo **Settings -> Secrets and variables -> Actions**:
   - **Secrets**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` for the
     scoped deploy IAM user (not the ingestion-only user in
     `infra/README.md` - that one only has S3 access; deploying needs
     `lambda:UpdateFunctionCode` / `ecs:UpdateService` on the specific
     resources, nothing broader).
   - **Variables**: `DEPLOY_ENABLED=true`, `AWS_REGION` (defaults to
     `ap-southeast-2` if unset), and whichever resource-name variables
     the real deploy commands need (e.g. `INGESTION_LAMBDA_NAME`).
3. Replace the placeholder `Deploy ingestion Lambda(s)` step in
   `cd.yml` with the real `aws lambda update-function-code` /
   `aws ecs update-service` commands for what you actually provisioned.
4. Add an environment protection rule on the `production` environment
   (Settings -> Environments) if you want a manual approval gate
   before each deploy, since this pushes real code to running
   infrastructure.

Until step 2-3 are done, `deploy` fails loudly (`exit 1`) rather than
silently doing nothing or deploying to a resource that doesn't exist
- that's deliberate, so turning `DEPLOY_ENABLED` on too early is
obvious in the Actions log rather than a quiet no-op.
