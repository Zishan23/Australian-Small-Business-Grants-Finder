# Infrastructure

Infrastructure as code for this project (Terraform or AWS CDK, to be decided) will live here.

Planned resources:
- S3 buckets (raw, processed)
- DynamoDB table for structured grant/compliance records
- SQS queue for decoupling ingestion and processing
- Lambda functions for lightweight processing and query handling
- ECS Fargate task definition and EventBridge Scheduler rule for the weekly ingestion job
- SNS topic for pipeline failure alerts
- One time EKS cluster manifest for the container orchestration demo (deployed and torn down same day)

## IAM user for ingestion

The ingestion pipeline needs an IAM user scoped only to the raw S3 bucket, not broad admin access. The policy is in iam-policy-grants-finder-ingestion.json.

To create the user and attach the policy via AWS CLI:

```
aws iam create-user --user-name grants-finder-ingestion

aws iam put-user-policy \
  --user-name grants-finder-ingestion \
  --policy-name grants-finder-raw-bucket-access \
  --policy-document file://infra/iam-policy-grants-finder-ingestion.json

aws iam create-access-key --user-name grants-finder-ingestion
```

The last command prints an AccessKeyId and SecretAccessKey. Copy those into your local .env (see .env.example), never into source code or the AWS CLI history you'd commit anywhere.

If you would rather use the console: create the user under IAM, choose "Attach policies directly" then "Create inline policy", switch to the JSON tab, and paste the contents of iam-policy-grants-finder-ingestion.json.

