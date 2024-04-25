from twisted.internet import defer

import time

import static.config as config
import log
import graph
import operations

scale_down_range_time = 60
scale_up_range_time = 60


def change_scale_policy(name, metric, value):
    config.default_scale_policy[name][metric] = value

def scaleDecision(graphObj, name, attrs, policy=config.default_scale_policy) -> int:
    decision = 0 # nothing

    timeNow = time.time()

    if attrs["cpu_stats"]["cpu_percent"] >= policy[attrs["type"]]["cpu_max"] and list(graphObj.predecessors(name)) and list(graphObj.successors(name)) and (timeNow - attrs["lastScaled"] > scale_up_range_time):
        decision = 1 # scale up
    elif attrs.get("scaled", False) and attrs["cpu_stats"]["cpu_percent"] <= policy[attrs["type"]]["cpu_min"] and attrs["cpu_stats"]["cpu_percent"] > 0 and (timeNow - attrs["lastScaled"] > scale_down_range_time):
        decision = 2 # scale down
    return decision


@defer.inlineCallbacks
def autoScale(socketObj, graphPods, graphNodes):
    log.printWithColor("[ autoScale ] start", type="INFO")
    scale_up_functions = {"BR": scaleUpBR, "NR": scaleUpNR, "NORMAL": createInstance}
    scale_down_functions = {"NR": scaleDownNR}
    for name, attrs in list(graphPods.nodes(data=True)):
        if attrs["scalable"] and name not in graph.locked_nodes:
            graph.locked_nodes.add(name)
            decision = scaleDecision(graphPods, name, attrs)
            if decision == 1:
                log.printWithColor("[ autoScale ] scale up " + name, type="INFO")
                yield scale_up_functions.get(attrs["type"], scaleUp)(socketObj, graphPods, graphNodes, name, attrs)
            elif decision == 2:
                log.printWithColor("[ autoScale ] scale down " + name, type="INFO")
                yield scale_down_functions.get(attrs["type"], scaleDown)(socketObj, graphPods, name, attrs)
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
def scaleUp(socketObj, graphObj, name, attrs):
    log.printWithColor("[ scaleUp ] start --------------", type="INFO")
    scale = attrs.get("scale", 1)
    in_node_names = list(graphObj.predecessors(name))
    out_node_names = list(graphObj.successors(name))
    lb_name = name + ".sr1"
    # if n == 1 -> no SRs so create one, else in_node_list is SRs
    log.printWithColor("[ scaleUp ]", "step 1", type="INFO")
    if scale == 1:
        # create SR
        if operations.createPodAndNode(lb_name, "sr", graphObj, socketObj, is_scalable=False):
            log.printWithColor("[ scaleUp ] " + lb_name + " created", type="INFO")

            #time.sleep(1)

            # set strategy to loadbalancing
            resp = yield socketObj.editConfig(lb_name, {"strategy": "loadbalancing"})
            if resp and "strategy" in resp:
                log.printWithColor("[ scaleUp ] " + " set " + lb_name + " strategy to loadbalancing", type="INFO")
                operations.attachNode(lb_name, in_node_names, [name])
        else:
            log.printWithColor("[ scaleUp ] When create Pod and add to graph. Step 2 aborded")
            operations.deletePodAndNode(graphObj, lb_name, namespace="ndn")
            return

        log.printWithColor("[ scaleUp ]" + " step 2 ", type="INFO")
        clone_name = name + "." + str(scale)
        # create a clone
        if operations.createPodAndNode(clone_name, attrs["type"].lower(), graphObj, socketObj, is_scalable=False):
            log.printWithColor("[ scaleUp ] " + clone_name + " created", type="INFO")
            # for each successor
            operations.attachNode(clone_name, [lb_name], out_node_names, True)
        else:
            log.printWithColor("[ scaleUp ] When try create Pod and add to graph. Step 2 aborded")
            operations.deletePodAndNode(graphObj, lb_name, namespace="ndn")
            operations.deletePodAndNode(graphObj, clone_name, namespace="ndn")
            return

        attrs["scale"] = scale + 1
        attrs["scaled"] = True
        attrs["lastScaled"] = time.time()
        log.printWithColor("[ scaleUp ] end --------------", type="INFO")

def choose_node_bad_placement(typeNode, microName, typeOperation):
    if typeNode == "sr":
        return "otavionew22-ideapad-gaming-3-15arh7"
    if typeNode == "br":
        return "otavionew22-ideapad-gaming-3-15arh7"
    else:
        return None
    
def choose_node_improvement_placement(graphPods, microName, graphNodes):
    if graphNodes.nodes[graphPods.nodes[microName]["nodeK8s"]]["microsDeployed"] < graphNodes.nodes[graphPods.nodes[microName]["nodeK8s"]]["microLimit"]:
        graphNodes.nodes[graphPods.nodes[microName]["nodeK8s"]]["microsDeployed"] = graphNodes.nodes[graphPods.nodes[microName]["nodeK8s"]]["microsDeployed"] + 1
        return graphPods.nodes[microName]["nodeK8s"]
    else:
        node_more_resource = ["node_name", 0]
        for node in graphNodes.nodes:
            capacity = graphNodes.nodes[node]["microLimit"]  - graphNodes.nodes[node]["microsDeployed"]
            if capacity > node_more_resource[1] and node not in ["otaviopc-to-be-filled-by-o-e-m"]:
                node_more_resource = [node, capacity]
        graphNodes.nodes[node_more_resource[0]]["microsDeployed"] = graphNodes.nodes[node_more_resource[0]]["microsDeployed"] + 1
        return node_more_resource[0]

@defer.inlineCallbacks
def scaleUpBR(socketObj, graphPods, graphNodes, name, attrs): 
    log.printWithColor("[ scaleUpBR ] start --------------", type="INFO")

    scale = attrs.get("scale", 1)
    in_node_list = list(graphPods.predecessors(name))
    out_node_list = list(graphPods.successors(name))
    lb_nodes_list = []

    # if n == 1 -> no SRs so create one, else in_node_list is SRs
    log.printWithColor("[ scaleUpBR ] step 1", type="INFO")
    if scale == 1:
        for i in range(len(in_node_list)):
            lb_name = name + ".sr" + str(i+1)
            # create and link SR to scaled node
            #node_for_deploy = choose_node_bad_placement("sr", lb_name, "scale_up")
            node_for_deploy = choose_node_improvement_placement(graphPods, name, graphNodes)
            if operations.createPodAndNode(lb_name, "sr", graphPods, socketObj, is_scalable=False, nodeName=node_for_deploy):
                log.printWithColor("[ scaleUpBR ] " + lb_name + " created", type="INFO")
                resp = yield socketObj.editConfig(lb_name, {"strategy": "loadbalancing"})
                #resp = {"strategy": True}
                if resp and "strategy" in resp:
                    log.printWithColor("[ scaleUpBR ] set " + lb_name + " strategy to loadbalancing", type="INFO")

                resp = yield operations.createFaceAndEdge(graphPods, socketObj, [lb_name], [name])
                if resp:
                    lb_nodes_list.append(lb_name)
                    resp = yield operations.createFaceAndEdge(graphPods, socketObj, [in_node_list[i]], [lb_name])
                    if resp:
                        resp = yield operations.delFaceAndEdge(graphPods, socketObj, [in_node_list[i]], [name])
                        if resp:
                            pass
                        else:
                            log.printWithColor("[ scaleUpBR ] When delete link " + in_node_list[i] + " to " + name + " Step 2 aborded", type="INFO")

                            yield operations.delFaceAndEdge(graphPods, socketObj, in_node_list[0:i], [lb_name])
                            yield operations.createFaceAndEdge(graphPods, socketObj, in_node_list[0:i-1], [lb_name])

                            log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                            operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                            return
                    else:
                        log.printWithColor("[ scaleUpBR ] When try link" + in_node_list[i] + " to " + lb_name + " Step 2 aborded", type="CRITICAL")

                        log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                        operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                        return
                else:
                    log.printWithColor("[ scaleUpBR ] When try link" + lb_name + " to " + name + " Step 2 aborded", type="CRITICAL")

                    log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                    operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                    return
            else:
                log.printWithColor("[ scaleUpBR ] When try create Pod and add to graph. Step 2 aborded", type="CRITICAL")

                log.printWithColor("[ scaleUpBR ] Delete " + lb_name, type="INFO")
                operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                return
    else:
        lb_nodes_list = in_node_list
    log.printWithColor("[ scaleUpBR ] " + "step 2", type="INFO")
    clone_name = name + "." + str(scale)
    
    #node_for_deploy = choose_node_bad_placement("br", clone_name, "scale_up")
    node_for_deploy = choose_node_improvement_placement(graphPods, name, graphNodes)
    if operations.createPodAndNode(clone_name, attrs["type"].lower(), graphPods, socketObj, is_scalable=False, nodeName=node_for_deploy):

        log.printWithColor("[ scaleUpBR ] " + clone_name + " created", type="INFO")
        for out_name in out_node_list:
            resp = yield socketObj.newFace(clone_name, out_name)
            if resp and resp > 0:
                log.printWithColor("[ scaleUpBR ] " + clone_name + " linked to " + out_name, type="INFO")
                graphPods.add_edge(clone_name, out_name, face_id=resp)

                #test
                #attrs["scalable"] = False
            else:
                log.printWithColor("[ scaleUpBR ] When try create face between " + clone_name + " and " + out_name + ". Step 2 aborded", type="CRITICAL")

                yield operations.delFaceAndEdge(graphPods, socketObj, in_node_list, [lb_name])
                yield operations.createFaceAndEdge(graphPods, socketObj, in_node_list, [name])
                
                log.printWithColor("[ scaleUpBR ] Deleting " + lb_name + " and " + clone_name, type="INFO")
                operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                operations.deletePodAndNode(graphPods, clone_name, namespace="ndn")
                return
            
        for idx, lb_name in enumerate(lb_nodes_list): # for lb_name in lb_nodes_list  ALTERADO
            resp = yield socketObj.newFace(lb_name, clone_name)
            if resp and resp > 0:
                log.printWithColor("[ scaleUpBR ] " + lb_name + " linked to " + clone_name, type="INFO")
                graphPods.add_edge(lb_name, clone_name, face_id=resp)
            else:
                log.printWithColor("[ scaleUpBR ] When try create face between " + lb_name + " and " + clone_name + ". Step 2 aborded", type="CRITICAL")
                
                yield operations.delFaceAndEdge(graphPods, socketObj, in_node_list, [lb_name])
                yield operations.createFaceAndEdge(graphPods, socketObj, in_node_list, [name])
                
                yield operations.delFaceAndEdge(graphPods, socketObj, lb_name[0:idx], [clone_name]) # preciso confererir
                
                for i in range(len(idx-1)):
                    yield socketObj.delFace(lb_name, i)
                
                operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
                operations.deletePodAndNode(graphPods, clone_name, namespace="ndn")
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
        
        operations.deletePodAndNode(graphPods, lb_name, namespace="ndn")
        operations.deletePodAndNode(graphPods, clone_name, namespace="ndn")
        return

def scaleUpNR(socketObj, graphPods, graphNodes, name, attrs):
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
