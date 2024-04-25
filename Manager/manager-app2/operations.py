import graph
import pod
import static.config as managerConfig
import log
import nodeK8s

from twisted.internet import defer, threads

import time

import networkx as nx
import traceback

import datetime


def createPodAndNode(podName, podType, graphObj, socketObj, namespace="ndn", is_scalable=True, nodeName=None):
    podObj = pod.createPodObj(podType, podName, nodeName=nodeName)
    if podObj:
        if pod.createPod(podObj, namespace=namespace, field_manager="ndn_manager"):
            APIresult = pod.getPodInfo(podName, namespace=namespace)
            IPaddr = pod.getPodIp(APIresult)
            nodeK8sName = nodeK8s.getNodeK8s(APIresult)

            customResourceName = False

            if IPaddr and nodeK8sName:
                if podType == "cs": 
                    customResourceName = podName + "-pod-monitor"
                    manifestPodMonitor = managerConfig.buildManifestPodMonitor(customResourceName, podName, "2s", "1s",)

                    if not pod.createCustomResource(manifestPodMonitor):
                        log.printWithColor("When create Pod monitor. Aborted", type="CRITICAL")
                        pod.deletePod(podName, namespace="ndn")
                        return False
                
                if graph.addPodToGraph(graphObj, podObj, IPaddr, podType, customResourceName, nodeK8sName, is_scalable=is_scalable, namespace=namespace):
                    socketObj.reportAddress(podName)
                    if graph.setLimits(graphObj, podObj):
                        log.printWithColor("Pod Created and added to graph", type="WARNING")
                        return True
                else:
                    pod.deletePod(podName, namespace="ndn")
                    if podType == "cs": 
                        pod.deleteCustomResource(customResourceName, namespaceParam="ndn")
                    return False
                
    return False

def deleteAllK8sResources(graphObj): 
    for node in graphObj.nodes(data=True):
        if node[1]["monitorName"]:
            pod.deleteCustomResource(node[1]["monitorName"], groupParam="monitoring.coreos.com", versionParam="v1", namespaceParam="ndn", pluralParam="podmonitors")
        pod.deletePod(node[0], namespace="ndn")
    print("Pods deleted")

def deleteAllPods(graphObj): 
    for node in graphObj.nodes():
        pod.deletePod(node, namespace="ndn")
    print("Pods deleted")


def deletePodAndNode(graphObj, podName, namespace="ndn"):
    try:
        if pod.deletePod(podName, namespace=namespace):
            if graphObj.has_node(podName):
                graphObj.remove_node(podName)
                return True
        else:
            return False
    except nx.NetworkXError as e:
        log.printWithColor("When try remove node ", e, type="CRITICAL")
        return False

@defer.inlineCallbacks
def detachNode(name, graphObj, socketObj):
    log.printWithColor("[ detachNode ] start", type="Warning")
    #       OUT
    #      / |
    #  3(del)|
    #    /   |
    #  NODE  1(add)
    #    \   |
    #  2(del)|
    #      \ |
    #       IN
    in_node_names = list(graphObj.predecessors(name))
    out_node_names = list(graphObj.successors(name))
    for out_node_name in out_node_names:
        for in_name in in_node_names:
            resp = yield socketObj.newFace(in_name, out_node_name)
            if resp and resp > 0:
                log.printWithColor("[ detachNode ] link " + in_name + " to " + out_node_name, type="Warning")
                graphObj.add_edge(in_name, out_node_name, face_id=resp)
                resp = yield socketObj.delFace(in_name, name)
                if resp:
                    log.printWithColor("[ detachNode ] unlink " + in_name + " and " + name, type="Warning")
                    graphObj.remove_edge(in_name, name)
        resp = yield socketObj.delFace(name, out_node_name)
        if resp:
            log.printWithColor("[ detachNode ] unlink " + name + " and " + out_node_name, type="Warning")
            graphObj.remove_edge(name, out_node_name)
    log.printWithColor("[ detachNode ] end ", type="Warning")


@defer.inlineCallbacks
def updateResourceStats(graphObj, mtgObj):    
    log.printWithColor("[ updateContainersStats ] start", type="INFO")

    nodes = list(graphObj.nodes(data=True))
    resps = yield defer.DeferredList([threads.deferToThread(mtgObj.getCpuAndMemory, node[0]) for node in nodes], consumeErrors=True)
    
    with open("cpuAndMemory.csv", "a") as f:
        timeNow = str(datetime.datetime.now().time())
        for node, resp in zip(nodes, resps):

            f.write(node[0] + "; ")
            f.write(timeNow + "; " )
            
            if resp[0]: #and resp[1] != False:
                if resp[1]["cpu"] != False and resp[1]["cpu"] !=0:
                    #cpu_percent = resources.calculePercent(node[1]["cpu_stats"]["cpu_total"], resp[1]["cpu"])
                    cpu_percent = resp[1]["cpu"]
                    graphObj.nodes[node[0]]["cpu_stats"]["cpu_percent"] = cpu_percent
                    
                    graphObj.nodes[node[0]]["cpu_stats"]["last_update"] = time.time()
                    log.printWithColor("[ updateContainersStats ] " + node[0] + " -> CPU: " + str(cpu_percent) + "%", type="INFO")
                else:
                    log.printWithColor("Pod " + node[0] + "  CPU usage equal 0", type="CRITICAL")
                    log.writeDataLogFile( "Pod "  + node[0] + " CPU usage equal 0", type="CRITICAL")

                f.write(str(graphObj.nodes[node[0]]["cpu_stats"]["cpu_percent"]) + "; ")
                
                if resp[1]["memory"] != False and resp[1]["memory"] != 0:
                    #memory_percent = resources.calculePercent(node[1]["memory_stats"]["memory_total"], resp[1]["memory"])
                    memory_percent = resp[1]["memory"]
                    graphObj.nodes[node[0]]["memory_stats"]["memory_percent"] = memory_percent

                    graphObj.nodes[node[0]]["memory_stats"]["last_update"] = time.time()
                    log.printWithColor("[ updateContainersStats ] " + node[0] + " -> Memory: " + str(memory_percent) + "%", type="INFO")
                else:
                    log.printWithColor("Memory usage equal 0", type="CRITICAL")
                    log.writeDataLogFile("Pod " + node[0] + " memory usage equal 0")

            f.write(str(graphObj.nodes[node[0]]["memory_stats"]["memory_percent"]) + "; ") # #alterar: mais uma identação a direita?
            
            f.write("\n")
    f.close()

    log.printWithColor("[ updateContainersStats ] end", type="INFO")


@defer.inlineCallbacks
def attachNode(name, in_node_names: list, out_node_names: list, graphObj, socketObj, new_link=False):
    
    print("\n")
    log.printWithColor("[ attachNode ] start", type="INFO")
    print("\n")

    # Process:
    #       OUT
    #      / |
    #  1(add)|
    #    /   |
    #  NODE  3(del)
    #    \   |
    #  2(add)|
    #      \ |
    #       IN
    # step 1

    for out_node_name in out_node_names:
        resp = yield socketObj.newFace(name, out_node_name)
        if resp and resp > 0:
            log.printWithColor("[ attachNode ] " + name + " linked to " + out_node_name, type="INFO")
            graphObj.add_edge(name, out_node_name, face_id=resp)
    # step 2
    for in_node_name in in_node_names:
        resp = yield socketObj.newFace(in_node_name, name)
        if resp and resp > 0:
            log.printWithColor("[ attachNode ] " + in_node_name + " linked to " + name, type="INFO")
            graphObj.add_edge(in_node_name, name, face_id=resp)
            # step 3
            if not new_link:
                for out_node_name in out_node_names:
                    if graphObj.has_edge(in_node_name, out_node_name):
                        resp = yield socketObj.delFace(in_node_name, out_node_name)
                        if resp and resp > 0:
                            log.printWithColor("[ attachNode ] " + in_node_name + " no longer linked to " + out_node_name, type="INFO")
                            graphObj.remove_edge(in_node_name, out_node_name)
    log.printWithColor("[ attachNode ] end", type="INFO")


@defer.inlineCallbacks
def delFaceAndEdge(graphObj, socketObj, podSources:list, podDestinations:list) -> bool:  
    try:
        for podSource in podSources: 
            for podDestination in podDestinations:
                log.printWithColor("Deleting link between " + podSource + " and " + podDestination, type="INFO")
                resp1 = yield socketObj.delFace(podSource, podDestination)
                if resp1:   
                    #log.printWithColor("Deleting edge " + podSource + " and " + podDestination, type="INFO")
                    graphObj.remove_edge(podSource, podDestination)
                else:
                    return False
        return True
    except Exception as e:
        log.printWithColor("When try delete face(s) and Edge(s). Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False    
    

"""
MELHORIA
Depois tenho que alterar a logica de createFaceAndEdge para possibilitar que medidas para 
retroagir ao estado passado sejam possível. 
Talvez eu faça isso passando [bool, indx] em  createFaceAndEdge() ou faça esse tratamento 
diretamente em createFaceAndEdge(). Inicialmente, parece ser melhor fora
"""

@defer.inlineCallbacks
def createFaceAndEdge(graphObj, socketObj, podSources:list, podDestinations:list) -> bool:  
    try:
        for podSource in podSources:
                for podDestination in podDestinations:
                    log.printWithColor("[ scaleUpBR ] Create link between " + podSource + " and " + podDestination, type="INFO")
                    resp2 = yield socketObj.newFace(podSource, podDestination)
                    if resp2 and resp2 > 0:   
                        #log.printWithColor("Add edge " + podSource + " and " + podDestination, type="INFO")
                        graphObj.add_edge(podSource, podDestination, face_id=resp2)
                    else:
                        return False
        return True
    except Exception as e:
        log.printWithColor("When try create new face(s) and Edge(s). Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        return False    
