from twisted.internet import defer

from kubernetes import utils

import time
from decimal import *

import static.config as managerConfig
import log
import graph
import operations

scale_down_range_time = 100
scale_up_range_time = 100

#graphNodesScale = None
#graphPodsScale = None

def change_scale_policy(name, metric, value):
    managerConfig.default_scale_policy[name][metric] = value

def scaleDecision(graphObj, name, attrs, policy=managerConfig.default_scale_policy) -> int:
    decision = 0 # nothing

    timeNow = time.time()

    if attrs["cpu_stats"]["cpu_percent"] >= policy[attrs["type"]]["cpu_max"] and list(graphObj.predecessors(name)) and list(graphObj.successors(name)) and (timeNow - attrs["lastScaled"] > scale_up_range_time):
        decision = 1 # scale up
    elif attrs.get("scaled", False) and attrs["cpu_stats"]["cpu_percent"] <= policy[attrs["type"]]["cpu_min"] and attrs["cpu_stats"]["cpu_percent"] > 0 and (timeNow - attrs["lastScaled"] > scale_down_range_time):
        decision = 2 # scale down
    return decision


@defer.inlineCallbacks
def autoScale(socketObj, graphPod, graphNodes):
    log.printWithColor("[ autoScale ] start", type="INFO")
    scale_up_functions = {"BR": scaleUpBR, "NR": scaleUpNR, "NORMAL": createInstance}
    scale_down_functions = {"NR": scaleDownNR}
    for name, attrs in list(graphPod.nodes(data=True)):
        if attrs["scalable"] and name not in graph.locked_nodes:
            graph.locked_nodes.add(name)
            decision = scaleDecision(graphPod, name, attrs)
            if decision == 1:
                log.printWithColor("[ autoScale ] scale up " + name, type="INFO")
                yield scale_up_functions.get(attrs["type"], scaleUp)(socketObj, graphPod, graphNodes, name, attrs)
            elif decision == 2:
                log.printWithColor("[ autoScale ] scale down " + name, type="INFO")
                yield scale_down_functions.get(attrs["type"], scaleDown)(socketObj, graphPod, name, attrs)
            elif decision == 0:
                log.printWithColor("[ autoScale ] " + name + " -> nothing to do", type="INFO")
            graph.locked_nodes.remove(name)
    log.printWithColor("[ autoScale ] end", type="INFO")


@defer.inlineCallbacks
def createInstance(socketObj, graphObj, name, attrs):
    scale = attrs.get("scale", 1)
    clone_name = name + "." + str(scale)
    
    in_node_names = list(graphObj.predecessors(name))
    out_node_names = list(graphObj.successors(name))
    # create a clone
    if operations.createPodAndNode(clone_name, attrs["type"].lower(), graphObj, socketObj, is_scalable=False):
        log.printWithColor("[ scaleUp ] " + clone_name + " created", type="INFO")
        # for each successor
        operations.attachNode(clone_name, in_node_names, out_node_names, True)
    else:
        log.printWithColor("[ scaleUp ] When create Pod and add to graph.")
        operations.deletePodAndNode(graphObj, clone_name,  namespace="ndn")
        return

    attrs["scale"] = scale + 1
    attrs["scaled"] = True
    log.printWithColor("[ scaleUp ] end", type="INFO")


@defer.inlineCallbacks
def scaleUp(socketObj, graphPod, graphNodes, name, attrs):
    log.printWithColor("[ scaleUp ] start --------------", type="INFO")
    scale = attrs.get("scale", 1)
    in_node_names = list(graphPod.predecessors(name))
    out_node_names = list(graphPod.successors(name))
    lb_name = name + ".sr1"
    # if n == 1 -> no SRs so create one, else in_node_list is SRs
    log.printWithColor("[ scaleUp ]", "step 1", type="INFO")
    if scale == 1:

        node_for_deploy = choose_node("sr", graphPod, graphNodes, in_node_names, out_node_names, lb_name, "scale_up") 

        # create SR
        if operations.createPodAndNode(lb_name, "sr", graphPod, socketObj, is_scalable=False, nodeName=node_for_deploy):
            log.printWithColor("[ scaleUp ] " + lb_name + " created", type="INFO")

            #time.sleep(1)

            # set strategy to loadbalancing
            resp = yield socketObj.editConfig(lb_name, {"strategy": "loadbalancing"})
            if resp and "strategy" in resp:
                log.printWithColor("[ scaleUp ] " + " set " + lb_name + " strategy to loadbalancing", type="INFO")
                operations.attachNode(lb_name, in_node_names, [name])
        else:
            log.printWithColor("[ scaleUp ] When create Pod and add to graph. Step 2 aborded")
            operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
            return

        log.printWithColor("[ scaleUp ]" + " step 2 ", type="INFO")
        clone_name = name + "." + str(scale)
        # create a clone

        node_for_deploy = choose_node(graphPod.nodes[name]["type"].str.lower(), graphPod, graphNodes, in_node_names, out_node_names, clone_name, "scale_up") 

        if operations.createPodAndNode(clone_name, attrs["type"].lower(), graphPod, socketObj, is_scalable=False):
            log.printWithColor("[ scaleUp ] " + clone_name + " created", type="INFO")
            # for each successor
            operations.attachNode(clone_name, [lb_name], out_node_names, True)
        else:
            log.printWithColor("[ scaleUp ] When try create Pod and add to graph. Step 2 aborded")
            operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
            operations.deletePodAndNode(graphPod, clone_name, namespace="ndn")
            return

        attrs["scale"] = scale + 1
        attrs["scaled"] = True
        attrs["lastScaled"] = time.time()
        log.printWithColor("[ scaleUp ] end --------------", type="INFO")


# return the sum limits for cpu and memory to each node
def sum_limits(graphPod, graphNodes) -> dict:
    dict_nodes = dict()
    nodes = graphPod.nodes(data=True)

    for node in nodes:
        if not (node[1]["nodeK8s"] in dict_nodes):
            dict_nodes[node[1]["nodeK8s"]] = {"cpu":node[1]["cpu_stats"]["cpu_total"], 
                                          "memory":node[1]["memory_stats"]["memory_total"]}
                        
        else:
            dict_nodes[node[1]["nodeK8s"]]["cpu"] =  dict_nodes[node[1]["nodeK8s"]]["cpu"] + node[1]["cpu_stats"]["cpu_total"]
            dict_nodes[node[1]["nodeK8s"]]["memory"] = dict_nodes[node[1]["nodeK8s"]]["memory"] + node[1]["memory_stats"]["memory_total"]

    # add nodes without NDN microservices deployed
    if len(dict_nodes) < len(graphNodes.nodes()): 
        all_nodes = graphNodes.nodes(data=True)
        dict_nodes_temp = dict_nodes
        for node1 in all_nodes:
            is_node = False
            for node2 in dict_nodes_temp:
                if not (node2 == node1[0]):
                    is_node = True
            if is_node:
                dict_nodes[node1[0]] = {"cpu":Decimal(0.0), 
                                        "memory":Decimal(0.0)} # without recource allocated to NDN microservices
    return dict_nodes


def get_in_and_out_node_with_resource(grathPod, nodes_candidates, in_node_names, out_node_names) -> list:
    nodes_chosen = list()

    for node in nodes_candidates:
        for in_node in in_node_names:
            if grathPod.nodes[in_node]["nodeK8s"] == node:
                nodes_chosen.append(grathPod.nodes[in_node]["nodeK8s"])
        for out_node in out_node_names:
            if grathPod.nodes[out_node]["nodeK8s"] == node:
                nodes_chosen.append(grathPod.nodes[out_node]["nodeK8s"])
    
    return nodes_chosen

def get_node_with_enough_resource(graphPod, graphNodes, cpu_micro, memory_micro) -> list:
    nodes_candidates = list()
    nodes_total_limits = sum_limits(graphPod, graphNodes)

    for node_name, node_attr in nodes_total_limits.items():
        cpu_limits = node_attr["cpu"] + cpu_micro
        memory_limits = node_attr["memory"] + memory_micro

        if (cpu_limits < graphNodes.nodes[node_name]["cpu"]) and (memory_limits < graphNodes.nodes[node_name]["memory"]):
            nodes_candidates.append(node_name)
    
    return nodes_candidates


def choose_node(typeNode, graphPod, graphNodes, in_node_names, out_node_names, microName, typeOperation):
    cpu_micro = Decimal(utils.parse_quantity(managerConfig.pod_default_attrs[typeNode]["limits"]["cpu"]))
    memory_micro = Decimal(utils.parse_quantity(managerConfig.pod_default_attrs[typeNode]["limits"]["memory"]))

    nodes_candidates = get_node_with_enough_resource(graphPod, graphNodes, cpu_micro, memory_micro)

    nodes_chosen = get_in_and_out_node_with_resource(graphPod, nodes_candidates, in_node_names, out_node_names)

    if len(nodes_chosen) > 0:
        nodes_chosen = nodes_chosen[0]
        return nodes_chosen
    else:
        log.printWithColor("[ERRO] When try choose a node to ", microName, type="CRITICAL")
        return False


@defer.inlineCallbacks
def scaleUpBR(socketObj, graphPod, graphNodes, name, attrs):
    log.printWithColor("[ scaleUpBR ] start --------------", type="INFO")

    scale = attrs.get("scale", 1)
    in_node_list = list(graphPod.predecessors(name))
    out_node_list = list(graphPod.successors(name))
    lb_nodes_list = []

    # if n == 1 -> no SRs so create one, else in_node_list is SRs
    log.printWithColor("[ scaleUpBR ] step 1", type="INFO")
    if scale == 1:
        for i in range(len(in_node_list)):
            lb_name = name + ".sr" + str(i+1)
            # create and link SR to scaled node
            node_for_deploy = choose_node("sr", graphPod, graphNodes, in_node_list, out_node_list, lb_name, "scale_up") 
            if operations.createPodAndNode(lb_name, "sr", graphPod, socketObj, is_scalable=False, nodeName=node_for_deploy):
                log.printWithColor("[ scaleUpBR ] " + lb_name + " created", type="INFO")
                #resp = yield socketObj.editConfig(lb_name, {"strategy": "loadbalancing"})
                resp = {"strategy": True}
                if resp and "strategy" in resp:
                    log.printWithColor("[ scaleUpBR ] set " + lb_name + " strategy to loadbalancing", type="INFO")

                resp = yield operations.createFaceAndEdge(graphPod, socketObj, [lb_name], [name])
                if resp:
                    lb_nodes_list.append(lb_name)
                    resp = yield operations.createFaceAndEdge(graphPod, socketObj, [in_node_list[i]], [lb_name])
                    if resp:
                        resp = yield operations.delFaceAndEdge(graphPod, socketObj, [in_node_list[i]], [name])
                        if resp:
                            pass
                        else:
                            log.printWithColor("[ scaleUpBR ] When delete link " + in_node_list[i] + " to " + name + " Step 2 aborded", type="INFO")

                            yield operations.delFaceAndEdge(graphPod, socketObj, in_node_list[0:i], [lb_name])
                            yield operations.createFaceAndEdge(graphPod, socketObj, in_node_list[0:i-1], [lb_name])

                            log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                            operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                            return
                    else:
                        log.printWithColor("[ scaleUpBR ] When try link" + in_node_list[i] + " to " + lb_name + " Step 2 aborded", type="CRITICAL")

                        log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                        operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                        return
                else:
                    log.printWithColor("[ scaleUpBR ] When try link" + lb_name + " to " + name + " Step 2 aborded", type="CRITICAL")

                    log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                    operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                    return
            else:
                log.printWithColor("[ scaleUpBR ] When try create Pod and add to graph. Step 2 aborded", type="CRITICAL")

                log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                return
    else:
        lb_nodes_list = in_node_list
    log.printWithColor("[ scaleUpBR ] " + "step 2", type="INFO")
    clone_name = name + "." + str(scale)
    
    node_for_deploy = choose_node("br", graphPod, graphNodes, in_node_list, out_node_list, clone_name, "scale_up")
    if operations.createPodAndNode(clone_name, attrs["type"].lower(), graphPod, socketObj, is_scalable=False, nodeName=node_for_deploy):

        log.printWithColor("[ scaleUpBR ] " + clone_name + " created", type="INFO")
        for out_name in out_node_list:
            resp = yield socketObj.newFace(clone_name, out_name)
            if resp and resp > 0:
                log.printWithColor("[ scaleUpBR ] " + clone_name + " linked to " + out_name, type="INFO")
                graphPod.add_edge(clone_name, out_name, face_id=resp)

                #test
                #attrs["scalable"] = False
            else:
                log.printWithColor("[ scaleUpBR ] When try create face between " + clone_name + " and " + out_name + ". Step 2 aborded", type="CRITICAL")

                yield operations.delFaceAndEdge(graphPod, socketObj, in_node_list, [lb_name])
                yield operations.createFaceAndEdge(graphPod, socketObj, in_node_list, [name])
                
                log.printWithColor("[ scaleUpBR ] Deleting " + lb_name + " and " + clone_name, type="INFO")
                operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                operations.deletePodAndNode(graphPod, clone_name, namespace="ndn")
                return
            
        for idx, lb_name in enumerate(lb_nodes_list): # for lb_name in lb_nodes_list  ALTERADO
            resp = yield socketObj.newFace(lb_name, clone_name)
            if resp and resp > 0:
                log.printWithColor("[ scaleUpBR ] " + lb_name + " linked to " + clone_name, type="INFO")
                graphPod.add_edge(lb_name, clone_name, face_id=resp)
            else:
                log.printWithColor("[ scaleUpBR ] When try create face between " + lb_name + " and " + clone_name + ". Step 2 aborded", type="CRITICAL")
                
                yield operations.delFaceAndEdge(graphPod, socketObj, in_node_list, [lb_name])
                yield operations.createFaceAndEdge(graphPod, socketObj, in_node_list, [name])
                
                yield operations.delFaceAndEdge(graphPod, socketObj, lb_name[0:idx], [clone_name]) # preciso confererir
                
                for i in range(len(idx-1)):
                    yield socketObj.delFace(lb_name, i)
                
                operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
                operations.deletePodAndNode(graphPod, clone_name, namespace="ndn")
                return
                
        attrs["scale"] = scale + 1
        attrs["scaled"] = True
        attrs["lastScaled"] = time.time()
        log.printWithColor("[ scaleUpBR ] end --------------", type="INFO")

    else:
        log.printWithColor("[ scaleUpBR ] When try create Pod and add to graph. Step 2 aborded", type="CRITICAL")
        
        for i in range(len(in_node_list)):
            yield socketObj.delFace(in_node_list[i], lb_name)
            yield socketObj.newFace(in_node_list[i], name)
        
        operations.deletePodAndNode(graphPod, lb_name, namespace="ndn")
        operations.deletePodAndNode(graphPod, clone_name, namespace="ndn")
        return

def scaleUpNR(name, attrs):
    log.printWithColor("[ scaleUpNR ] pass")
    pass

@defer.inlineCallbacks
def scaleDown(socketObj, graphObj, name, attrs):
    log.printWithColor("[ scaleDown ] start --------------", type="INFO")

    scale = attrs["scale"] - 1
    lb_node_list = list(graphObj.predecessors(name))
    out_node_list = list(graphObj.successors(name))
################ Step1 ################
    log.printWithColor("[ scaleDown ] step 1", type="INFO")
    clone_name = name + "." + str(scale)
    
    # for each SR
    resp = yield operations.delFaceAndEdge(graphObj, socketObj, lb_node_list, [clone_name])
    if resp:
        #print("Ok")
        pass
    else:
        log.printWithColor("[ scaleDown ] Aborted", type="CRITICAL")
        #resp = operations.createFaceAndEdge(graphObj, socketObj, lb_node_list[0:idx-1], [clone_name]) 
        return

    # for each successor
    resp = yield operations.delFaceAndEdge(graphObj, socketObj, [clone_name], out_node_list)
    if resp:
        pass
    else:
        log.printWithColor("[ scaleDown ] Aborted", type="CRITICAL")
        resp = yield operations.createFaceAndEdge(graphObj, socketObj, lb_node_list, [clone_name]) 

        #resp = operations.createFaceAndEdge(graphObj, socketObj, out_node_list[0:idx-1], [clone_name]) 
        return
################ Step2 ################
    # remove last clone
    resp1 = operations.deletePodAndNode(graphObj,clone_name, namespace="ndn") 
    if resp1:
        log.printWithColor("[ scaleDown ] " + clone_name +  " Deleted", type="INFO")
        log.printWithColor("[ scaleDown ] step 2", type="INFO")
        attrs["scale"] = scale
        # if no clone
        if scale == 1:
            # for each SR
            for lb_name in lb_node_list:
                # for each predecessor
                for in_name in list(graphObj.predecessors(lb_name)):
                    # link SR predecessor to node 
                    resp = yield operations.createFaceAndEdge(graphObj, socketObj, [in_name], [name])
                    if resp and resp > 0:
                        # unlink SR predecessor and SR
                        resp = yield operations.delFaceAndEdge(graphObj, socketObj, [in_name], [lb_name])
                        if resp and resp > 0:
                        # unlink SR and node
                            resp = yield operations.delFaceAndEdge(graphObj, socketObj, [lb_name], [name])
                            if resp and resp > 0:     
                                pass
                            else:
                                log.printWithColor("[ scaleDown ] When try delete face between " + lb_name + " and " + name + ". Aboted", type="CRITICAL")
                                return
                        else:
                            log.printWithColor("[ scaleDown ] When try delete face between " + in_name + "and " + lb_name + ". Aboted", type="CRITICAL")
                            return
                    else:
                        log.printWithColor("[ scaleDown ] When try create face between " + in_name + "and " + name + ". Aboted", type="CRITICAL")
                        return
                # remove SR
                resp2 = operations.deletePodAndNode(graphObj, lb_name, namespace="ndn")
                if resp2:
                    log.printWithColor("[ scaleDown ] " + lb_name +  " Deleted", type="INFO")
                    log.printWithColor("[ scaleDown ] Success", type="INFO")
                    attrs["lastScaled"] = time.time()
                else:
                    log.printWithColor("[ scaleDown ] When try delete " + lb_name + ". Aboted", type="CRITICAL")
                    return
            attrs["scaled"] = False
    else:
        log.printWithColor("[ scaleDown ] When remove last clone" + clone_name + ". Aborted", type="CRITICAL")
    
    log.printWithColor("[ scaleDown ] end --------------", type="INFO")


def scaleDownNR(name, attrs):
    log.printWithColor("[ scaleDownNR ] pass", type="INFO")
    pass
