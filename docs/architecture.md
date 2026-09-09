# Architecture

## Overview

(Add architecture diagram here, e.g. exported from draw.io or excalidraw as architecture.png, referenced below)

![Architecture diagram](architecture.png)

## Data flow

1. EventBridge Scheduler triggers a weekly ingestion run
2. ECS Fargate task fans out to per source scrapers/API clients under src/ingestion/sources
3. Raw responses are written to S3 under raw/{source}/{date}/
4. A processing step cleans and normalizes records into a common schema, writing to S3 under processed/{source}/{date}/ and to DynamoDB for fast lookups
5. New or updated records are chunked and embedded, with embeddings stored for retrieval (via Bedrock)
6. SQS decouples ingestion completion from downstream processing so failures in one source do not block others
7. SNS sends an alert if any stage fails
8. At query time, a multi agent pipeline (eligibility agent, compliance agent, retrieval agent) routes the user's question, retrieves relevant chunks, and generates an answer with source citations

## Common record schema (draft)

```json
{
  "source": "string",
  "title": "string",
  "description": "string",
  "eligibility": "string",
  "amount": "string",
  "deadline": "date or null",
  "category": "string",
  "state_or_territory": "string or null",
  "url": "string",
  "ingested_at": "timestamp"
}
```

## Cost notes

(Track actual AWS costs here as the project runs, to compare against the ~$100 AUD budget)

## Decisions log

- Chose serverless (Lambda + SQS + DynamoDB) over always on compute to keep costs low and predictable
- ECS Fargate reserved for the weekly ingestion job only, since it needs longer running time and more memory than Lambda's limits comfortably allow for scraping and parsing
- EKS used once for a same day, torn down demonstration to show container orchestration familiarity without ongoing cost
