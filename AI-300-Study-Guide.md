# Study Guide — Exam AI-300: Operationalizing Machine Learning and Generative AI Solutions

> Source: [Microsoft Learn — AI-300 study guide](https://learn.microsoft.com/credentials/certifications/resources/study-guides/ai-300)
> Pass mark: **700 / 1000**. Renew annually via a free online assessment on Microsoft Learn.

---

## Useful links

| Link | Description |
|---|---|
| [How to earn the certification](https://learn.microsoft.com/credentials/certifications/operationalizing-machine-learning-and-generative-ai-solutions/) | Exam requirements and certification path |
| [Certification renewal](https://learn.microsoft.com/credentials/certifications/renew-your-microsoft-certification) | Free annual renewal assessment |
| [Exam scoring and score reports](https://learn.microsoft.com/credentials/certifications/exam-scoring-reports) | 700 or greater required to pass |
| [Exam sandbox](https://aka.ms/examdemo) | Explore the exam environment before test day |
| [Request accommodations](https://learn.microsoft.com/credentials/certifications/request-accommodations) | Extra time, assistive devices, or other modifications |

---

## Audience profile

You should have subject matter expertise in setting up infrastructure for **machine learning operations (MLOps)** and **generative AI operations (GenAIOps)** on Azure. This includes:

- Training, optimizing, deploying, and maintaining traditional ML models with **Azure Machine Learning**
- Deploying, evaluating, monitoring, and optimizing generative AI applications and agents with **Microsoft Foundry**
- Python programming and entry-level DevOps (GitHub Actions, CLI)
- MLOps tooling: Azure Machine Learning, Foundry, GitHub Actions, Bicep / Azure CLI

---

## Skills at a glance

| Skill area | Weight |
|---|---|
| Design and implement an MLOps infrastructure | 15–20% |
| Implement machine learning model lifecycle and operations | 25–30% |
| Design and implement a GenAIOps infrastructure | 20–25% |
| Implement generative AI quality assurance and observability | 10–15% |
| Optimize generative AI systems and model performance | 10–15% |

---

## 1 · Design and implement an MLOps infrastructure (15–20%)

### Create and manage resources in a Machine Learning workspace
- Create and manage a workspace
- Create and manage datastores
- Create and manage compute targets
- Configure identity and access management for workspaces

### Create and manage assets in a Machine Learning workspace
- Create and manage data assets
- Create and manage environments
- Create and manage components
- Share assets across workspaces by using registries

### Implement IaC for Machine Learning
- Configure GitHub integration with Machine Learning to enable secure access
- Deploy Machine Learning workspaces and resources by using Bicep and Azure CLI
- Automate resource provisioning by using GitHub Actions workflows
- Restrict network access to Machine Learning workspaces
- Manage source control for machine learning projects by using Git

---

## 2 · Implement machine learning model lifecycle and operations (25–30%)

### Orchestrate model training
- Configure experiment tracking with MLflow
- Use automated machine learning to explore optimal models
- Use notebooks for experimentation and exploration
- Automate hyperparameter tuning
- Run model training scripts
- Manage distributed training for large and deep learning models
- Implement training pipelines
- Compare model performance across jobs

### Implement model registration and versioning
- Package a feature retrieval specification with the model artifact
- Register an MLflow model
- Evaluate a model by using responsible AI principles
- Manage model lifecycle, including archiving models

### Deploy machine learning models for production environments
- Deploy models as real-time or batch endpoints with managed inference options
- Test and troubleshoot model endpoints
- Implement progressive rollout and safe rollback strategies

### Monitor and maintain machine learning models in production
- Detect and analyze data drift
- Monitor performance metrics of models deployed to production
- Configure retraining or alert triggers when thresholds are exceeded

---

## 3 · Design and implement a GenAIOps infrastructure (20–25%)

> **Workshop coverage:** Labs 01–06 map primarily to this skill area.

### Implement Foundry environments and platform configuration
- Create and configure Foundry resources and project environments ← **Labs 01, 02, 03**
- Configure identity and access management with managed identities and RBAC ← **Labs 01, 05, 06**
- Implement network security and private networking configurations ← **Lab 05**
- Deploy infrastructure using Bicep templates and Azure CLI ← **Lab 06**

### Deploy and manage foundation models for production workloads
- Deploy foundation models by using serverless API endpoints and managed compute options ← **Labs 01–04**
- Select appropriate models for specific use cases
- Implement model versioning and production deployment strategies
- Configure provisioned throughput units for high-volume workloads

### Implement prompt versioning and management with source control
- Design and develop prompts
- Create prompt variants and compare performance across different prompts
- Implement version control for prompts by using Git repositories ← **Lab 02 (Variant C / GitOps)**

---

## 4 · Implement generative AI quality assurance and observability (10–15%)

> **Workshop coverage:** Labs 04 and 07 map primarily to this skill area.

### Configure evaluation and validation for generative AI applications and agents
- Create test datasets and data mapping for comprehensive model evaluation ← **Lab 07**
- Implement AI quality metrics, including groundedness, relevance, coherence, and fluency ← **Lab 07**
- Configure risk and safety evaluations for harmful content detection ← **Lab 07**
- Set up automated evaluation workflows by using built-in and custom evaluation metrics ← **Lab 07**

### Implement observability for generative AI applications and agents
- Examine continuous monitoring in Foundry ← **Lab 04**
- Monitor performance metrics, including latency, throughput, and response times ← **Lab 04**
- Track and optimize cost metrics, including token consumption and resource usage ← **Lab 04**
- Configure detailed logging, tracing, and debugging capabilities for production troubleshooting ← **Labs 02, 03, 04, 06**

---

## 5 · Optimize generative AI systems and model performance (10–15%)

### Optimize retrieval-augmented generation (RAG) performance and accuracy
- Optimize retrieval performance by tuning similarity thresholds, chunk sizes, and retrieval strategies
- Select and fine-tune embedding models for domain-specific use cases and accuracy improvements
- Implement and optimize hybrid search approaches combining semantic and keyword-based retrieval
- Evaluate and improve RAG system performance by using relevance metrics and A/B testing frameworks

### Implement advanced fine-tuning and model customization
- Design and implement advanced fine-tuning methods
- Create and manage synthetic data for fine-tuning
- Monitor and optimize fine-tuned model performance
- Manage a fine-tuned model from development through production deployment

---

## Workshop → exam objective cross-reference

| Lab | Primary skill area | Key objectives practised |
|---|---|---|
| **01** Basic Agent | GenAIOps infrastructure | Foundry project setup, keyless auth, serverless endpoints |
| **02** MCP Tool Agent | GenAIOps infrastructure | Tool deployment patterns, GitOps prompt versioning, observability intro |
| **03** Custom Function Tool | GenAIOps infrastructure | Tool design decisions, function-as-tool pattern, debugging tool calls |
| **04** Tracing Agent | Quality assurance & observability | OTel pipeline, App Insights, KQL for latency and token cost |
| **05** Sidecar / Entra Agent ID | GenAIOps infrastructure | Per-agent managed identity, network security, RBAC |
| **06** Weather MCP + Azure Functions | GenAIOps infrastructure | Bicep IaC deployment, Entra Easy Auth, end-to-end distributed tracing |
| **07** Red Teaming | Quality assurance & observability | Risk/safety evaluation, ASR metric, automated evaluation workflows |
