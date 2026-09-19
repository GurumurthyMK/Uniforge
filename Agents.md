AWS-FIRST CONSTRAINT

UniForge is intended to run on AWS Free Tier / low-cost AWS infrastructure.

Every architectural decision must consider:

- compute cost
- database cost
- storage cost
- network transfer
- operational complexity
- deployment simplicity

Prefer:
- modular monolith
- PostgreSQL
- S3 for files
- stateless API
- lightweight background processing
- simple REST APIs
- server-side pagination
- bounded graph queries

Avoid unless justified:
- microservices
- Kubernetes
- service meshes
- dedicated graph databases
- Kafka
- Elasticsearch/OpenSearch
- Redis
- Lambda-heavy architectures
- unnecessary managed services

The goal is not to maximize the number of AWS services used.

The goal is to build the smallest reliable architecture that demonstrates UniForge's differentiating capabilities and can scale conceptually later.