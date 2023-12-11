from kubernetes import client
from kubernetes.client.rest import ApiException

# def getNodeResource():
#     ret_metrics = api_client.call_api(
#                 '/api/v1/nodes', 'GET',
#                 auth_settings=['BearerToken'], response_type='json', _preload_content=False)
#     response = ret_metrics[0].data.decode('utf-8')
#     response_json = json.loads(response)
    
#     len_nodes = len(json.loads(response)["items"])
#     for i in len_nodes:
#         node_name = response_json["items"][i]["metadata"]["name"]
#         node_CPU = response_json["items"][i]["status"]["allocatable"]["cpu"]
#         node_Memory = response_json["items"][i]["status"]["allocatable"]["memory"]
        
#         graphNodes.add_node(node_name, CPU_total = node_CPU, memory_total = node_Memory)

