from kubernetes import client
from kubernetes.client.rest import ApiException

listK8sNodes = []

def getAllK8sNodesInfo(): 
    try:
        k8s_api = client.CoreV1Api()
        response = k8s_api.list_node()

        if len(response.items) > 0:
            for node in response.items:
                listK8sNodes.append(node.metadata.name)
        
        return listK8sNodes
    
    except ApiException as e:
        print('Found exception in reading the logs')

def getNodeK8s(APIresult):
    try:
        return APIresult.spec.node_name
    except Exception as e:
        print(e)
        return False