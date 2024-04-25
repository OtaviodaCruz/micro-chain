from decimal import *

import networkx as nx

from twisted.internet import reactor, defer
from twisted.internet.task import LoopingCall

import datetime

from klein import Klein

import static.server as appServer
import operations
import log
import UDP_communication 
import scale
import monitoring
import pod
import static.NR as NR
import static.config as managerConfig

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException

## Declare objects
app = Klein()

graphPods = nx.DiGraph()

modules_socket = UDP_communication.ModulesSocket(graphPods)

log.init()

log.fileLogConfig("manager.log")

def configK8s():
    try:
        # load authenication from kube-config
        # I think that kube-conf is a file named config in $HOME/.kube. 
        # This file have information about: cluster, users, namespaces, authentication mechanisms
        config.load_incluster_config()
        return True
    except Exception as e:
        print("Error getting kubernetes client")
        return False


if not configK8s():
    exit()

try:
    pod.plusSendCount()

    resp = client.CoreV1Api().read_namespaced_service(name="prometheus-kube-prometheus-prometheus", namespace='default')
    
    pod.plusReceiveCount()

    monitor_address = str(resp.spec.cluster_ip)
    mtgObj = monitoring.Monitoring('http://' + monitor_address + ':9090/')
    
except ApiException as e:
    print('Error When try get prometheus service address')
    mtgObj = monitoring.Monitoring()

# ------------------------------------------------ Init node graphs ------------------------------------------------

graphNodes = nx.Graph()

#"count(node_cpu_seconds_total{mode="'"idle"'"}) by (instance)"
#kube_pod_container_resource_limits{resource="cpu"}
#kube_pod_container_resource_limits
query_cpu = "sum(machine_cpu_cores) by (node)"
result_cpu = mtgObj.runQuery(query_cpu)

for result in result_cpu["data"]["result"]:
    graphNodes.add_node(result["metric"]["node"])
    graphNodes.nodes[result["metric"]["node"]]["cpu"] = Decimal(utils.parse_quantity(result["value"][1]))

query_memory =  "sum(machine_memory_bytes) by (node)"
result_memory= mtgObj.runQuery(query_memory)


for result in result_memory["data"]["result"]:
    graphNodes.nodes[result["metric"]["node"]]["memory"] = Decimal(utils.parse_quantity(result["value"][1]))


graphNodes.nodes["otaviopc-to-be-filled-by-o-e-m"]["microsDeployed"] = 0
graphNodes.nodes["otaviopc-to-be-filled-by-o-e-m"]["microLimit"] = 0

graphNodes.nodes["otavioold22-n450-p-be56p1"]["microsDeployed"] = 0
graphNodes.nodes["otavioold22-n450-p-be56p1"]["microLimit"] = 3

graphNodes.nodes["otavionew22-ideapad-gaming-3-15arh7"]["microsDeployed"] = 0
graphNodes.nodes["otavionew22-ideapad-gaming-3-15arh7"]["microLimit"] = 3


print(graphNodes.nodes(data=True))
#-------------------------------------------------Periodic Call-------------------------------------------------
@defer.inlineCallbacks
def controllLoopResource():
    yield operations.updateResourceStats(graphPods, mtgObj)
    yield scale.autoScale(modules_socket, graphPods, graphNodes)
    #print(scale.choose_node("sr", graphPods, graphNodes, "cs1", "br1", "cs2", "scale_up"))

def controllLoopMetrics():
    mtgObj.verifyMetrics(graphPods)
    
def saveOnCSV():
    with open("communication.csv", "a") as f:
        timeNow = str(datetime.datetime.now().time())

        # communication manager and microsserviços
        f.write(timeNow + ";" + modules_socket.stringToCSV())

        # communication manager and monitoring module
        f.write(mtgObj.stringToCSV()) 

        # communication manager and orchestrator module
        f.write(pod.stringToCSV()) 

        f.write("\n")
        
        f.close()

def testCreateNode(typeMicro, is_scalable=True, nodeName=None):
    name = typeMicro + str(managerConfig.graph_counters[typeMicro])
    managerConfig.graph_counters[typeMicro] += 1
    
    if operations.createPodAndNode(name, typeMicro, graphPods, modules_socket, namespace="ndn", is_scalable=is_scalable, nodeName=nodeName):
        return name
    log.printWithColor("When try create " + name)
    return False

@defer.inlineCallbacks
def testLinkNodes(sourceNode, destinationNode):
    log.printWithColor("Creating link between", type="INFO")
    if (graphPods.has_node(sourceNode) and graphPods.has_node(destinationNode)
            and not graphPods.has_edge(sourceNode, destinationNode)):
        resp = yield modules_socket.newFace(sourceNode, destinationNode)#, j.get("producer", False) if graph.nodes[destinationNode]["type"] == "NR" else False)
        if resp and resp > 0:
            graphPods.add_edge(sourceNode, destinationNode, face_id=resp)
            NR.appendExistingRoutes(graphPods, modules_socket, sourceNode, destinationNode)
            log.printWithColor("Link between " + sourceNode + " and " + destinationNode + "created", type="INFO")
            return "1"
        else:
            log.printWithColor("When try create Link between " + sourceNode + " and " + destinationNode, type="CRITICAL")
            log.writeDataLogFile("When try create Link between " + sourceNode + " and " + destinationNode, type="CRITICAL")
            return "0"
    else:
        log.printWithColor("When try create Link between " + sourceNode + " and " + destinationNode + ". One node don't exist.", type="CRITICAL")
        log.writeDataLogFile("When try create Link between " + sourceNode + " and " + destinationNode + ". One node don't exist.", type="CRITICAL")
        return "0"

def placementMicroservice(micro_list: list):
    count = 0
    #position_list = [] 
    for micro in micro_list:
        if micro["name"] == "client" or micro["name"] == "server":
            None
        else:
            if graphNodes.nodes[micro_list[count - 1]["node"]]["microsDeployed"] < graphNodes.nodes[micro_list[count - 1]["node"]]["microLimit"]:
                #position_list.append(micro_list[count - 1]["node"])
                micro["node"] = micro_list[count - 1]["node"]
                graphNodes.nodes[micro_list[count - 1]["node"]]["microsDeployed"] = graphNodes.nodes[micro_list[count - 1]["node"]]["microsDeployed"] + 1
            else:  
                node_more_resource = ["node_name", 0]
                for node in graphNodes.nodes:
                    capacity = graphNodes.nodes[node]["microLimit"]  - graphNodes.nodes[node]["microsDeployed"]
                    if capacity > node_more_resource[1]:
                        node_more_resource = [node, capacity]
                #position_list.append(node_more_resource[0])
                micro["node"] = node_more_resource[0]
                graphNodes.nodes[node_more_resource[0]]["microsDeployed"] = graphNodes.nodes[node_more_resource[0]]["microsDeployed"] + 1
        count = count + 1

def experimentSetup1():

    #chain: cs - br - nr
    microservice_chain = [{"name": "client", "node": "otavionew22-ideapad-gaming-3-15arh7"},
     {"name": "cs", "node": "not chosen"},
     {"name": "br", "node": "not chosen"},
     {"name": "nr", "node": "not chosen"},  
     {"name": "server", "node": "otavionew22-ideapad-gaming-3-15arh7"}
     ]
    
    placementMicroservice(microservice_chain)
    
    print(microservice_chain)

    microCS = testCreateNode("cs", nodeName=microservice_chain[1]["node"])
    microBR = testCreateNode("br", is_scalable=True, nodeName=microservice_chain[2]["node"])
    microNR = testCreateNode("nr", nodeName=microservice_chain[3]["node"])

    #testLinkNodes(microCS, microNR)

    testLinkNodes(microCS, microBR)
    testLinkNodes(microBR, microNR)
    
def experimentSetup2():
    
    microCS = testCreateNode("cs", nodeName="otavioold22-n450-p-be56p1")
    microBR = testCreateNode("br", is_scalable=True, nodeName="otavionew22-ideapad-gaming-3-15arh7")
    microNR = testCreateNode("nr", nodeName="otavioold22-n450-p-be56p1")

    #testLinkNodes(microCS, microNR)

    testLinkNodes(microCS, microBR)
    testLinkNodes(microBR, microNR)

if __name__ == "__main__":
    LoopingCall(controllLoopResource).start(20)

    LoopingCall(controllLoopMetrics).start(5)

    LoopingCall(saveOnCSV).start(5)

    reactor.suggestThreadPoolSize(10) 

    appServer.serverGraph = graphPods
    appServer.serverSocket = modules_socket

    #nodeK8s.getAllK8sNodesInfo()

    experimentSetup1()

    log.printWithColor("Init manager", type="INFO")

    reactor.run()

    log.printWithColor("Kill manager", type="INFO")
    
    operations.deleteAllK8sResources(graphPods)