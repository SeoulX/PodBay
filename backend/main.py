from fastapi import FastAPI
from kubernetes import client, config

app = FastAPI()

# Load kubeconfig from your ~/.kube/config (Minikube)
config.load_kube_config()

@app.get("/api/pods")
def list_pods():
    v1 = client.CoreV1Api()
    pods = v1.list_pod_for_all_namespaces(watch=False)
    return [
        {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
        }
        for pod in pods.items
    ]

@app.get("/api/nodes")
def list_nodes():
    v1 = client.CoreV1Api()
    nodes = v1.list_node()
    return [
        {
            "name": node.metadata.name,
            "cpu": node.status.capacity.get("cpu"),
            "memory": node.status.capacity.get("memory"),
        }
        for node in nodes.items
    ]
