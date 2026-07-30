import json
from services.claude_service import extract_keywords

sample_jd = """

SAMPLECOMPANY is seeking enthusiastic AI Engineers to design, build, and deploy intelligent systems. The role offers hands-on opportunities with large language models, AI agents, 
classical ML pipelines, and deep learning architectures on GCP.

Responsibilities
Building Python applications powered by LLMs (GPT, Claude, Gemini, LLaMA), utilizing prompt engineering, evaluation, and model customization techniques
Developing Retrieval-Augmented Generation (RAG) pipelines with vector databases (FAISS, ChromaDB, Pinecone) and frameworks like LangChain or LlamaIndex
Designing and constructing agent workflows that use planning, tool calling, and memory for reliable multi-step tasks, leveraging frameworks such as LangChain, LlamaIndex, CrewAI, or AutoGen
Evaluating and improving model outputs using automated metrics and human feedback
Training and deploying ML models for classification, regression, and clustering using Python libraries like scikit-learn and XGBoost
Performing feature engineering, data preprocessing, and exploratory data analysis on both structured and unstructured datasets
Building deep learning models with PyTorch or TensorFlow for NLP and computer vision tasks
Applying transfer learning and optimizing models for production (quantization, distillation)
Building web applications and REST APIs with Flask or FastAPI to serve ML, deep learning, and LLM-powered features to end users
Designing API endpoints for model inference, data retrieval, and integration with frontend applications
Integrating AI capabilities into web services with robust error handling, authentication, and scalable architecture
Deploying and managing ML, deep learning, and generative AI workloads on Google Cloud Platform (Vertex AI, Cloud Run, GKE, BigQuery)
Using Vertex AI for training, serving, and orchestrating pipelines across traditional ML models, deep learning models, and LLM-based applications
Working with GCP storage (Cloud Storage, BigQuery) for data pipelines and feature stores
Containerizing applications with Docker for deployment on GKE or Cloud Run
Writing Python scripts for data pipelines, API integrations, and automation tasks on GCP
Monitoring deployed ML/DL/LLM models and setting up retraining and evaluation workflows using GCP tools

Required
Bachelor's or Master's in CS, AI, Data Science, or related field
1+ years of experience (internships, research, or personal projects count)
Strong proficiency in Python (NumPy, Pandas, Flask/FastAPI) and Hugging Face ecosystem
Hands-on experience with LLMs, including prompt engineering, evaluation, or building LLM-powered applications
Understanding of ML fundamentals: supervised/unsupervised learning, model evaluation, and feature engineering
Deep learning concepts knowledge (Transformers, CNNs, attention mechanisms), with experience in PyTorch or TensorFlow
Experience with at least one major cloud platform; GCP strongly preferred
Familiarity with Linux, Git, Docker, and building REST APIs using Flask or FastAPI
Understanding of databases and SQL for querying and integrating structured data (PostgreSQL, MySQL, BigQuery, MongoDB, or similar)
Continuous learner with a growth mindset who keeps up with rapidly evolving AI research, tools, and best practices
Strong communication skills for explaining complex technical concepts to both technical and non-technical stakeholders
Team-oriented mindset with a collaborative approach to problem-solving, code reviews, and knowledge sharing
Good documentation habits for writing clear technical docs and maintaining well-commented code

"""

result = extract_keywords(sample_jd)
print(json.dumps(result.model_dump(exclude={"raw_response"}), indent=2))
