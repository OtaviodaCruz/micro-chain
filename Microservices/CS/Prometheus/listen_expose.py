from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, defer

import simplejson as json

import traceback

from prometheus_client import Gauge

from prometheus_client.twisted import MetricsResource

from twisted.web.resource import Resource
from twisted.web.server import Site

from decimal import *

import log 

log.init()
log.fileLogConfig("expose.log")

class Monitoring:
    def __init__(self, monitorPort = 8000):
        self.monitorPort = monitorPort
        self.listenServer()
    
    def listenServer(self):
        try:
            root = Resource()
            root.putChild(b'metrics', MetricsResource())
            reactor.listenTCP(self.monitorPort, Site(root))
            
            print("Listen monitoring on port " + str(self.monitorPort))
        except Exception as e:
            print("When try listen" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            log.writeDataLogFile("When try listen", type="ERROR")
            return False

monitor = Monitoring()

#######################################################################

def jsonSerial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, set):
        return list(obj)
    raise TypeError("Type %s not serializable" % type(obj))

class MonitorCS():
    
    def __init__(self):

        self.hitCountObj = Gauge('hit_count', 'Number of requested WITH local cache')
        self.missCountObj = Gauge('miss_count', 'Number of requested WITHOUT local cache')

    def exportCsMetrics(self, hitCountVal, missCountVal):
        #self.cacheHitObj.inc(1.6)  
        #self.hitCountObj.inc(1.6) 
        #self.missCountObj.inc(1.6) 

        self.hitCountObj.set(hitCountVal) 
        self.missCountObj.set(missCountVal) 

monitorCsObj = MonitorCS()

class ModulesSocket(DatagramProtocol): 
    def __init__(self):
        self.routes = {"report": self.handleReport}
        self.report_routes = {"cache_status": self.handleCacheStatusReport}
        # self.request_routes = {"route_registration": self.handlePrefixRegistration}
        # self.reply_results = {"add_face": "face_id", "del_face": "status", "edit_config": "changes", "add_route": "status", "del_route": "status", "add_keys": "status", "del_keys": "status"}
        
        self.request_counter = 1
        self.pending_requests = {}

        self.initListen()

    def datagramReceived(self, data, addr):
        try:
            dataDecode = json.loads(data.decode())
            self.routes.get(dataDecode.get("type", None), self.unknown)(dataDecode, addr)
        except ValueError:  
            print("Decoding JSON has failed:" + data.decode())
            log.writeDataLogFile("Decoding JSON has failed", type="ERROR")
        except Exception as e :  
            print("Unknown error: ", e)
            log.writeDataLogFile("Unknown error", type="ERROR")

    def unknown(self, j: dict, addr):
        print(json.dumps(j))

    def initListen(self):
        reactor.listenUDP(9999, self, maxPacketSize=1 << 16)

    def handleReport(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.report_routes.get(j.get("action", None), self.unknown)(j, addr)
    
    def handleCacheStatusReport(self, j: dict, addr):
        if all(field in j for field in ["hit_count", "miss_count"]) :
            hit_count = j["hit_count"] #- cache_stats["hit_count"]
            miss_count = j["miss_count"] #- cache_stats["miss_count"]
                   
            monitorCsObj.exportCsMetrics(hit_count, miss_count)

    def editConfig(self, source, data: dict):
        json_data = {"action": "edit_config", "id": self.request_counter}
        json_data.update(data)

        print("Sending command editConfig to", source)

        return self.sendDatagram(json_data, source, 10000)
    
    def removeRequest(self, value, key):
        self.pending_requests.pop(key, None)
        return value
    
    def sendDatagram(self, data: dict, ip, port):
        try:
            d = defer.Deferred()
            d.addTimeout(5, reactor, onTimeoutCancel=self.onTimeout)
            d.addBoth(self.removeRequest, self.request_counter)
            self.pending_requests[self.request_counter] = d
            self.request_counter += 1
            
            self.transport.write(json.dumps(data, default=jsonSerial).encode(), (ip, port))
            return d
        except Exception as e:
            print("Unknown error when try send Datagram" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            log.writeDataLogFile("Unknown error when try send Datagram" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="ERROR")

            return False
    
    def onTimeout(self, result, timeout):
        print("Got {0!r} but actually timed out after {1} seconds".format(result, timeout))
        log.writeDataLogFile("Got {0!r} but actually timed out after {1} seconds".format(result, timeout), type="ERROR")

        return None
    

socket = ModulesSocket()

#### RUN #####
reactor.run()
