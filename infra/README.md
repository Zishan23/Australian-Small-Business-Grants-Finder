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
