import time
import requests  
import simplejson as json

from prometheus_client.twisted import MetricsResource

from twisted.internet import reactor, defer
from twisted.web.resource import Resource
from twisted.web.server import Site

from decimal import *

import log

import traceback

import datetime

class Monitoring:
    def __init__(self, monitorAddress= 'http://localhost:9090/', monitorPort = 8000):
        self.monitorAddress = monitorAddress
        self.monitorPort = monitorPort

        self.metricsReceive = {"receiveCount": 0, "receiveBytes":0}
        self.metricsSend = {"sendCount": 0, "sendBytes":0}

        self.listenServer()
    
    def receivePerformance(self, data:dict):
        for metric in self.metricsReceive:
            if metric in data:
                self.metricsReceive[metric] = self.metricsReceive[metric] + data[metric]

    def getReceivePerformance(self):
        return self.metricsReceive

    def resetCountReceive(self):
        for metrics in self.metricsReceive:
            self.metricsReceive[metrics] = 0

    def sendPerformance(self, data:dict):
        for metric in self.metricsSend:
            if metric in data:
                self.metricsSend[metric] = self.metricsSend[metric] + data[metric]

    def getSendPerformance(self):
        return self.metricsSend

    def resetCountSend(self):
        for metrics in self.metricsSend:
            self.metricsSend[metrics] = 0

    def stringToCSV(self):
        stringData = ""
        recevePerf = self.getReceivePerformance()
        stringData = stringData + str(recevePerf["receiveCount"]) + ";"
        stringData = stringData + str(recevePerf["receiveBytes"]) + ";"
        
        sendPerf = self.getSendPerformance()
        stringData = stringData + str(sendPerf["sendCount"]) + ";" 
        stringData = stringData + str(sendPerf["sendBytes"]) + ";" 

        self.resetCountSend()
        self.resetCountReceive()

        return stringData

    def listenServer(self):
        try:
            root = Resource()
            root.putChild(b'metrics', MetricsResource())
            reactor.listenTCP(self.monitorPort, Site(root))
            
            log.printWithColor("Listen monitoring on port " + str(self.monitorPort), type="INFO")
        except Exception as e:
            log.printWithColor("When try listen" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("When try listen", str(e.args[0]), type="CRITICAL")
            return False

    def runQuery(self, query:str, timeout=5) -> dict:
        try:

            self.sendPerformance({"sendCount": 1, "sendBytes":0})

            response = requests.get(self.monitorAddress + '/api/v1/query', params={'query': query}, timeout=timeout)   

            response.raise_for_status()
            r_content = response.content

            self.receivePerformance({"receiveCount": 1, "receiveBytes":len(r_content)})
            
            return json.loads(r_content.decode('utf-8'))
            
        except requests.exceptions.ConnectionError as errcConnection:
            log.printWithColor("Connection" + ". Specification: " + str(errcConnection.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("Connection", str(errcConnection.args[0]), type="CRITICAL")
            return False
        except requests.exceptions.HTTPError as errHTTP:
            log.printWithColor("HTTP" + ". Specification: " + str(errHTTP.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("HTTP", str(errHTTP.args[0]), type="CRITICAL")
            return False  
        except requests.exceptions.Timeout as errTimeout:
            log.printWithColor("Timeut during run monitoring query" + ". Specification: " + str(errTimeout.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("Timeut during run monitoring query", type="CRITICAL")
            return False   
        except requests.exceptions.RequestException as e:
            log.printWithColor("During run query" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("During run query", type="CRITICAL")
            return False  

    def getCpu(self, podName:str)-> Decimal:        
        query = '(sum(irate(container_cpu_usage_seconds_total{pod=' + '"' + podName + '"' +', container!="", service="prometheus-kube-prometheus-kubelet"}[1m])) / sum(kube_pod_container_resource_limits{pod=' + '"' + podName + '"' + ', resource="cpu"})) * 100'
        result = self.runQuery(query)

        if result['status'] == 'success':            
            return Decimal(result["data"]["result"][0]["value"][1])
        else:
            print ("else")
            return False

    def getMemory(self, podName:str)-> Decimal:       
        query = '(sum(max(container_memory_working_set_bytes{container!="", pod='  + '"' + podName + '"' + '} OR container_memory_rss{container!="", pod='  + '"' + podName + '"' + '})) / sum(kube_pod_container_resource_limits{pod=' + '"' + podName + '"' + ', resource="memory"})) * 100'        
        result = self.runQuery(query)

        if result['status'] == 'success':
            return Decimal(result["data"]["result"][0]["value"][1])
        else:
            return False

    def getCpuAndMemory(self, podName:str)-> dict:
        resultCpu = self.getCpu(podName)
        resultMemory = self.getMemory(podName)
        
        return {"cpu": resultCpu,
                "memory": resultMemory}
    
    def verifyMetrics(self, graphObj):
        log.printWithColor("[ UPDATE METRICS ] start", type="INFO")
        try:
            for node in graphObj.nodes(data=True):

                if node[1]["metrics"]:
                    now = time.time()
                    for key, value in node[1]["metrics"].items():
                        if (value["status"] == "on") and (((now - value["lastTime"])) > (value["timeStep"]/1000)):
                            result = value["function"](self, node[0])
                            if result:
                                graphObj.nodes[node[0]]["metrics"][key]["lastTime"] = now
                                graphObj.nodes[node[0]]["metrics"][key]["currentValue"] = result
                                
                                #print(result)

            log.printWithColor("[ UPDATE METRICS ] end", type="INFO")
            return True 
        except Exception as e:
            log.printWithColor("During verify metrics" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
            log.writeDataLogFile("During verify metrics", type="CRITICAL")
            return False  