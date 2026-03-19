# 🚀 Autonomous DevEx Platform (ADEP)

## 📌 Overview

ADEP is a simple internal developer platform that automates:

* Build → Test → Deploy
* Monitoring and debugging
* Basic data processing
* AI-assisted failure analysis

This project simulates how modern teams manage applications using CI/CD, Kubernetes, and observability tools.

---

## ⚙️ Tech Stack

* Python
* Docker
* Kubernetes
* GitHub Actions
* Prometheus & Grafana (planned)
* Terraform (planned)

---

## 🏗️ How It Works

1. Developer pushes code
2. CI/CD pipeline runs
3. Docker image is built
4. Application is deployed to Kubernetes
5. Metrics and logs are collected
6. Failures can be analyzed

---

## 🚀 Getting Started

### Run locally

```bash
docker build -t adep-app -f docker/Dockerfile .
docker run -p 5000:5000 adep-app
```

---

### Run with Kubernetes

```bash
kind create cluster --name adep
kubectl apply -f k8s/deployment.yaml
kubectl port-forward deployment/adep-app 5000:5000
```

---

## 📁 Structure

```
app/        # application code
docker/     # Dockerfile
k8s/        # Kubernetes configs
docs/       # design docs
```

---

## 🧭 Roadmap

* [x] Basic app + Docker
* [x] Kubernetes deployment
* [ ] CI/CD pipeline
* [ ] Monitoring (Prometheus/Grafana)
* [ ] AI failure analyzer

---

## 🎯 Goal

Build a realistic, end-to-end platform that demonstrates:

* CI/CD pipelines
* Cloud-native deployment
* Observability
* Automation
