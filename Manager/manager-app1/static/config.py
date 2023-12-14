import monitorCS 

# Global Variables ----------------------------------------------------------------------------------------------------------------
# max attempts
max_attempt = 2

#near_to_server = "otaviopc1-270e5j-2570ej"
#near_to_client = "otaviopc2-270e5j-2570ej"

default_scale_policy = {"CS": {"cpu_max": 80, "cpu_min": 20, "memory_max":0, "memory_min":0}, 
                "BR": {"cpu_max": 65, "cpu_min": 25, "memory_max":70, "memory_min":25}, 
                "NR": {"cpu_max": 80, "cpu_min": 20, "memory_max":0, "memory_min":0}
                }

graph_counters = {"cs": 1, "br": 1, "nr": 1, "sr": 1, "sv": 1, "pd": 1, "la": 1, "fw": 1}

node_default_stats = {
    "cpu_stats": {
        "cpu_percent": 0.0,
        "cpu_total": 0,
        "last_update": 0.0,
    },
    "memory_stats": {
        "memory_percent": 0.0,
        "memory_total": 0,
        "memory_update": 0.0,
    }
}

specific_node_default_attrs = {
    "cs": {
        "type": "CS",
        #"size": 100000, #quantidade absoluta de conteudos que é possivel salvar (não é em Mb)
        "lastScaled": 0.0
    },
    "br": {
        "type": "BR",
        #"size": 250,
        "lastScaled": 0.0
    },
    "nr": {
        "type": "NR",
        "static_routes": {},
        "dynamic_routes": {},
        "lastScaled": 0.0
    },
    "sr": {
        "type": "SR",
        "strategy": "multicast",
        "lastScaled": 0.0
    }
}

default_metrics = {
    "cs": {"hit_count": {"status": "off", "currentValue": 0.0, "lastTime": 0.0, "timeStep": 0.0, "function": monitorCS.getHitCount}, 
        "miss_count": {"status": "off", "currentValue": 0.0, "lastTime": 0.0, "timeStep": 0.0, "function": monitorCS.getMissCount},
        "size_usage": {"status": "off", "currentValue": 0.0, "lastTime": 0.0, "timeStep": 0.0, "function": monitorCS.getMissCount}},
    "br": {},
    "nr": {},
    "sr": {},
    "pd": {},
    }


pod_default_attrs = {
    "cs": {
    "container_name": "microservice-content-store",
    "container_image": "otaviocruz/ndn_microservice-content_store:8.0",
    "template_labels": {"app": "microservice-content-store"},
    "limits":{"cpu": "100m", "memory": "85M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    },
    "nr": {
    "container_name": "microservice-name-router",
    "container_image": "otaviocruz/ndn_microservice-name_router:4.0",
    "template_labels": {"app": "microservice-name-router"},
    "limits":{"cpu": "100m", "memory": "20M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    },
    "br": {
    "container_name": "microservice-backward-router",
    "container_image": "otaviocruz/ndn_microservice-backward_router:3.0",
    "template_labels": {"app": "microservice-backward-router"},
    "limits":{"cpu": "25m", "memory": "35M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    },
    "sr": {
    "container_name": "microservice-strategy-forwarder",
    "container_image": "otaviocruz/ndn_microservice-strategy_forwarder:2.0",
    "template_labels": {"app": "microservice-strategy-forwarder"},
    "limits":{"cpu": "100m", "memory": "20M"} # 500m -> 0.5 (50%) of 1 core CPU. 300M -> 300 megabytes
    }
}

# prometheus_podMonitor_manifest = {
#     "apiVersion": "monitoring.coreos.com/v1",
#     "kind": "PodMonitor",
#     "metadata": {"name": "pod-app-exp", "labels": {"release": "prometheus"}},
#     "spec":{
#     "selector":{
#         "matchLabels":{
#             "app": "pod-app-exp"
#         }
#     },
#     "podMetricsEndpoints":  
#     [{"port": "metrics"}, {"interval": "2s"}, {"scrapeTimeout": "1s"}]
#     }
# }

def buildManifestPodMonitor(name:str, app:str, interval:str, scrapeTimeout:str, port:str="metrics") -> dict:

    prometheus_podMonitor_manifest = {
        "apiVersion": "monitoring.coreos.com/v1",
        "kind": "PodMonitor",
        "metadata": {"name": name, "labels": {"release": "prometheus"}},
        "spec":{
        "selector":{
            "matchLabels":{
                "app": app
            }
        },
        "podMetricsEndpoints":  
        [{"port": port}, {"interval": interval}, {"scrapeTimeout": scrapeTimeout}]
        }
    }

    return prometheus_podMonitor_manifest

command_default = {
    "cs": "/CS",
    "nr": "/NR",
    "br": "/BR",
    "sr": "/SR"
}

arg_default = {
    "cs": {"size": "100000", "local_port": "6363", "command_port": "10000"},
    "nr": {"consumer_port": "6362", "producer_port": "6363","command_port": "10000"},
    "br": {"size":"250", "local_port": "6363", "command_port": "10000"},
    "sr": {"local_port": "6363", "command_port": "10000"}
}

# def set_args(pod_type, pod_name, container_arg, add_arg = []) -> list:
#     if pod_type == "cs":
#         return ["-n", pod_name, "-s", container_arg["size"], "-p", container_arg["local_port"], "-C", container_arg["command_port"]] + add_arg
#     elif pod_type == "br":
#         return ["-n", pod_name, "-s", container_arg["size"], "-p", container_arg["local_port"], "-C", container_arg["command_port"]] + add_arg
#     elif pod_type == "nr":
#         return ["-n", pod_name, "-c", container_arg["consumer_port"], "-p", container_arg["producer_port"], "-C", container_arg["command_port"]] + add_arg
#     elif pod_type == "sr":
#         return ["-n", pod_name, "-p", container_arg["local_port"], "-C", container_arg["command_port"]] + add_arg
#     else:
#         return False



def set_args(pod_type, pod_name, container_arg, add_arg = "") -> str:
    if pod_type == "cs":
        return " -n " + pod_name + " -s " + container_arg["size"] + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "br":
        return " -n " + pod_name + " -s " + container_arg["size"] + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "nr":
        return " -n " + pod_name + " -c " + container_arg["consumer_port"] + " -p " + container_arg["producer_port"] + " -C " + container_arg["command_port"] + add_arg
    elif pod_type == "sr":
        return " -n " + pod_name + " -p " + container_arg["local_port"] + " -C " + container_arg["command_port"] + add_arg
    else:
        return False
