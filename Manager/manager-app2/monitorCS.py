import traceback
import log
from prometheus_client import Gauge

def getHitCount(monitoringObj, podName, endpoint="metrics"):

    try:
        query = "hit_count{endpoint=" + "'" + endpoint + "'" + ", pod=" + "'" + podName +"'" "}"
        result = monitoringObj.runQuery(query)

        if len(result["data"]["result"]) > 0:
            return result["data"]["result"][0]["value"][1]
        else:
            return False
        
    except Exception as e:               
        log.printWithColor("When try get Hit Count from Monitor module" + podName  + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        log.writeDataLogFile("When try get Hit Coun from Monitor module" + podName  + ". Error: " + str(e), type="CRITICAL")    
        return False
    

def getMissCount(monitoringObj, podName, endpoint="metrics"):
    try:
        query = "miss_count{endpoint=" + "'" + endpoint + "'" + ", pod=" + "'" + podName +"'" "}"
        result = monitoringObj.runQuery(query)

        if len(result["data"]["result"]) > 0:
            return result["data"]["result"][0]["value"][1]
        else:
            return False
        
    except Exception as e:               
        log.printWithColor("When try get Miss Count from Monitor module" + podName  + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        log.writeDataLogFile("When try get Miss Count from Monitor module" + podName  + ". Error: " + str(e), type="CRITICAL")    
        return False
    

def getSizeUsage(monitoringObj, podName, endpoint="metrics"):
    try:
        query = "size_usage{endpoint=" + "'" + endpoint + "'" + ", pod=" + "'" + podName +"'" "}"
        result = monitoringObj.runQuery(query)

        if len(result["data"]["result"]) > 0:
            return result["data"]["result"][0]["value"][1]
        else:
            return False

    except Exception as e:               
        log.printWithColor("When try get size usage Miss from Monitor module" + podName  + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
        log.writeDataLogFile("When try get size usag from Monitor module" + podName  + ". Error: " + str(e), type="CRITICAL")    
        return False


def verifyScaleCS():
    pass
"""     try:
        if cache_stats["cache_hit"] < 0.8 * old_ratio:
            name = j["name"] + ".SV1"
            if not graph.has_node(name) and createContainer(name, "SV"):
                graph.add_node(name,  editable=False, scalable=False, addresses=getContainerIPAddresses(name),
                                **copy.deepcopy(node_default_attrs), **copy.deepcopy(specific_node_default_attrs["SV"]))
                addKeysToSV(name)
                yield attachNode(name, [j["name"]], list(graph.successors(j["name"])))
                lp = LoopingCall(IncreaseSVExpirationCounter, name)
                lp.start(2)
                SVs_to_check[name] = lp
    except Exception as e:
        print(e) """