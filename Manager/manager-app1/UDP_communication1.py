from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor, defer

import simplejson as json

import time

import static.NR as NR
import log
import static.server as appServer

import socket

import traceback

class ModulesSocket(DatagramProtocol): 
    def __init__(self, graph):
        self.routes = {"report": self.handleReport, "request": self.handleRequest, "reply": self.handleReply}
        self.report_routes = {"producer_disconnection": self.handleProducerDisconnectionReport, "invalid_signature": self.handleInvalidSignatureReport}
        self.request_routes = {"route_registration": self.handlePrefixRegistration}
        self.reply_results = {"add_face": "face_id", "del_face": "status", "edit_config": "changes", "add_route": "status", "del_route": "status", "add_keys": "status", "del_keys": "status"}
        
        self.graph = graph
        self.request_counter = 1
        self.pending_requests = {}

        ## -------Metrics---------
        self.receiveCount = 0
        self.sendCount = 0

        self.receiveBytes = 0
        self.sendBytes = 0

        metricsReceive = {"receiveCount": 0, "receiveBytes":0
                        }
        
        metricsSend = {"sendCount": 0, "sendBytes":0
                    }

        ## Server listen 
        self.initListen()

    def receivePerformance(self, data:dict):
        for metric in self.metricsReceive:
            self.metricsReceive[metric] = data[metric]

    receivePerformance({"receiveCount": 1, "receiveBytes":2})

    def receivePerformance(self, bytesVal, countVal = 1):
        self.receiveCount = self.receiveCount + countVal
        self.receiveBytes = self.receiveBytes + bytesVal

    def getReceivePerformance(self):
        self.receiveCount = 0
        self.receiveBytes = 0

    def resetCountReceive(self):
        self.receiveCount = 0
        self.receiveBytes = 0

    def sendPerformance(self, bytesVal, countVal = 1):
        self.sendCount = self.sendCount + countVal
        self.sendBytes = self.sendBytes + bytesVal

    def resetCountSend(self):
        self.sendCount = 0
        self.sendBytes = 0

    def datagramReceived(self, data, addr):
        try:
            j = json.loads(data.decode())
            self.routes.get(j.get("type", None), self.unknown)(j, addr)
            
            print("Receive data: ", type(data)) 

            self.receivePerformance(len(data))
        
        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            log.printWithColor("Decoding JSON has failed:" + data.decode())

    def unknown(self, j: dict, addr):
        log.printWithColor(json.dumps(j))

    def handleReport(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.report_routes.get(j.get("action", None), self.unknown)(j, addr)

    def face_error(self, j: dict, addr):
        if all(field in j for field in ["face_id"]) and self.graph.has_node(j["name"]):
            print(j["name"], "droped package")

    def handleInvalidSignatureReport(self, j: dict, addr):
        log.printWithColor("[ handleInvalidSignatureReport ]", json.dumps(j), type="INFO")
        if all(field in j for field in ["invalid_signature_names"]) and self.graph.has_node(j["name"]):
            packet_stats = self.graph.nodes[j["name"]]["packet_stats"]
            packet_stats["fake_count"] += len(j["invalid_signature_names"])
            packet_stats["last_update"] = time.time()

    def handleProducerDisconnectionReport(self, j: dict, addr):
        if all(field in j for field in ["face_id"]) and self.graph.has_node(j["name"]):
            prefixes = list(self.graph.nodes[j["name"]]["static_routes"].pop(j["face_id"], set()))
            if prefixes:
                NR.propagateDelRoutes(j["name"], prefixes)

    def handleRequest(self, j: dict, addr):
        if all(field in j for field in ["name", "action"]):
            self.request_routes.get(j.get("action", None), self.unknown)(j, addr)

    def handlePrefixRegistration(self, j: dict, addr):
        log.printWithColor("[ handlePrefixRegistration ]" + json.dumps(j), type="WARNING")
        if all(field in j for field in ["face_id", "prefix"]) and self.graph.has_node(j.get("name", None)):
            data = {"action": "reply", "id": j.get("id", 0), "result": True}
            self.sendDatagram(data, addr[0], addr[1])
            routes = self.graph.nodes[j["name"]].get("routes", {})
            face_routes = routes.get(j["face_id"], set())
            face_routes.add(j["prefix"])
            routes[j["face_id"]] = face_routes
            self.graph.nodes[j["name"]]["routes"] = routes
            #NR.propagateNewRoutes(self.graph, self, j["name"], [j["prefix"]])

    def handleReply(self, j: dict, addr):
        log.printWithColor("[ handleReply ]" + str(json.dumps(j)), type="WARNING")
        deferred = self.pending_requests.get(j.get("id", 0), None)
        if deferred:
            deferred.callback(j.get(self.reply_results.get(j.get("action", "unknown"), "unknown"), None))
        else:
            log.printWithColor(self.pending_requests, type="WARNING")

    def editConfig(self, source, data: dict):
        source_addrs = self.graph.nodes[source]["addresses"]
        json_data = {"action": "edit_config", "id": self.request_counter}
        json_data.update(data)

        log.printWithColor("Sending command editConfig to " + source, type="WARNING")

        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def newFace(self, source, target, port=6363):
        try:
            source_addrs = self.graph.nodes[source]["addresses"]
            target_addrs = self.graph.nodes[target]["addresses"]
            json_data = {"action": "add_face", "id": self.request_counter, "layer": "tcp", "address": target_addrs["data"], "port": 6362 if self.graph.nodes[target]["type"] == "NR" else 6363}

            log.printWithColor("Sending command new face to " + source, type="WARNING")

            return self.sendDatagram(json_data, source_addrs["command"], 10000)
        except Exception as e:
                log.printWithColor("Unknown error when try execute newFace()" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
                return False

    def delFace(self, source, target):
        source_addrs = self.graph.nodes[source]["addresses"]
        face_id = self.graph.edges[source, target]["face_id"]
        json_data = {"action": "del_face", "id": self.request_counter, "face_id": face_id}

        log.printWithColor("Sending command delete face to " + source, type="WARNING")
        
        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def newRoute(self, source, face_id, prefixes: (list, set)):
        source_addrs = self.graph.nodes[source]["addresses"]
        json_data = {"action": "add_route", "id": self.request_counter, "face_id": face_id, "prefixes": prefixes}

        log.printWithColor("Sending command new route to " +source, type="WARNING")
        
        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def delRoute(self, source, face_id, prefix: str):
        source_addrs = self.graph.nodes[source]["addresses"]
        json_data = {"action": "del_route", "id": self.request_counter, "face_id": face_id, "prefix": prefix}

        log.printWithColor("Sending command new route to " + source, type="WARNING")
        
        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def list(self, source):
        source_addrs = self.graph.nodes[source]["addresses"]
        json_data = {"action": "list", "id": self.request_counter}
        
        log.printWithColor("Sending command list to " + source, type="WARNING")

        return self.sendDatagram(json_data, source_addrs["command"], 10000)

    def sendDatagram(self, data: dict, ip, port):
        try:
            # print("[", str(datetime.datetime.now()), "]", "send", data, "to", ip, port)
            # deferred to fire when the corresponding reply is received
            d = defer.Deferred()
            d.addTimeout(5, reactor, onTimeoutCancel=self.onTimeout)
            d.addBoth(self.removeRequest, self.request_counter)
            self.pending_requests[self.request_counter] = d
            self.request_counter += 1

            dataBytes = json.dumps(data, default=appServer.jsonSerial).encode()

            self.sendPerformance(len(dataBytes))
            
            self.transport.write(dataBytes, (ip, port))
            return d
        except Exception as e:
            log.printWithColor("Unknown error when try send Datagram" + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()))
            return False

    def onTimeout(self, result, timeout):
        log.printWithColor("Got {0!r} but actually timed out after {1} seconds".format(result, timeout), type="CRITICAL")
        return None

    def removeRequest(self, value, key):
        #print("[", str(datetime.datetime.now()), "]", value, key)
        self.pending_requests.pop(key, None)
        return value

    @defer.inlineCallbacks
    def reportAddress(self, podName, portAddr=int(9999)) -> bool: 
        max_attempt = 2

        for attempt in range(max_attempt + 1):   
            try:
                self.graph.nodes[podName]["addresses"]
                d = {}

                hostname = socket.gethostname()
                IPAddr = socket.gethostbyname(hostname)

                d["manager_address"] = IPAddr
                d["manager_port"] = portAddr
                resp = yield self.editConfig(podName, d)

                if resp != None:
                    log.printWithColor("Manager IP sended to " + podName, type="WARNING")
                    return True
                if attempt > max_attempt:
                    log.printWithColor("When try get IP pod " + podName , type="CRITICAL")
                    log.writeDataLogFile("When try get IP pod " + podName, type="CRITICAL")    
                    return False

            except Exception as e:               
                log.printWithColor("When try get IP pod " + podName  + ". Specification: " + str(e.args[0]) + ". " + str(traceback.format_exc()), type="CRITICAL")
                log.writeDataLogFile("When try get IP pod " + podName  + ". Error: " + str(e), type="CRITICAL")    
                return False
                
    def initListen(self):
        reactor.listenUDP(9999, self, maxPacketSize=1 << 16)
